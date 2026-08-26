from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from panimau_bot.config import Settings
from panimau_bot.constants import SOCIAL_URL_FILTER_PATTERN
from panimau_bot.handlers.attachments import ATTACHMENT_FILTER, handle_attachment
from panimau_bot.handlers.callbacks import handle_cancel
from panimau_bot.handlers.commands import (
    admin_broadcast,
    export_feedback,
    health_check,
    show_stats,
    show_version,
    start,
    submit_feedback,
    tell_joke,
)
from panimau_bot.handlers.social import handle_social_link
from panimau_bot.models import AppServices, PendingStore
from panimau_bot.release import APP_VERSION, CHANGELOG
from panimau_bot.services.downloader import SocialVideoDownloader
from panimau_bot.services.state import BotState
from panimau_bot.services.vk_archive import ArchiveRepublisher, publish_scheduled_post
from panimau_bot.stats import BotStats
from panimau_bot import voice

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_startup(application: Application) -> None:
    """Обновить меню и один раз объявить текущую версию в беседе."""
    services = application.bot_data["services"]
    if not isinstance(services, AppServices):
        return

    try:
        await application.bot.set_my_commands(
            (
                BotCommand("start", "прочитать светлый контракт"),
                BotCommand("health", "проверить котел и обе головы"),
                BotCommand("stats", "открыть книгу поставок"),
                BotCommand("joke", "выслушать вторую голову"),
                BotCommand("feedback", "оставить жалобу или предложение"),
                BotCommand("version", "показать редакцию контракта"),
                BotCommand("help", "повторно зачитать устав"),
            )
        )
    except Exception:
        logger.exception("Не удалось обновить меню команд")

    if services.archive is not None and application.job_queue is not None:
        try:
            await asyncio.to_thread(services.archive.ensure_queue)
        except Exception:
            logger.exception("Не удалось разобрать заветные запасы")
        delay = services.archive.resume_pending_schedule()
        if delay is not None:
            application.job_queue.run_once(publish_scheduled_post, delay)

    if services.state.has_announced(APP_VERSION):
        return

    try:
        await application.bot.send_message(
            chat_id=services.settings.group_id,
            text=voice.render_changelog(APP_VERSION, CHANGELOG),
            disable_notification=True,
        )
        services.state.mark_announced(APP_VERSION)
    except Exception:
        logger.exception("Не удалось объявить версию %s в беседе", APP_VERSION)


def build_application(settings: Settings | None = None) -> Application:
    """Создаёт и настраивает приложение бота."""
    app_settings = settings or Settings.from_env()
    application = (
        Application.builder()
        .token(app_settings.bot_token)
        .post_init(on_startup)
        .build()
    )

    state = BotState(app_settings.state_dir)
    archive = ArchiveRepublisher(app_settings, state) if app_settings.vk_service_token else None

    application.bot_data["services"] = AppServices(
        settings=app_settings,
        stats=BotStats(),
        pending_store=PendingStore(),
        downloader=SocialVideoDownloader(),
        state=state,
        archive=archive,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("joke", tell_joke))
    application.add_handler(CommandHandler("feedback", submit_feedback))
    application.add_handler(CommandHandler("feedback_export", export_feedback))
    application.add_handler(CommandHandler("version", show_version))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & filters.Regex(SOCIAL_URL_FILTER_PATTERN),
            handle_social_link,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ATTACHMENT_FILTER,
            handle_attachment,
        )
    )
    application.add_handler(CallbackQueryHandler(handle_cancel, pattern=r"^cancel_"))
    application.add_error_handler(error_handler)

    return application


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок."""
    logger.error("Ошибка у бота:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        services = context.application.bot_data.get("services")
        disable_notification = (
            isinstance(services, AppServices)
            and update.effective_message.chat_id == services.settings.group_id
        )
        await update.effective_message.reply_text(
            voice.render_general_error(),
            disable_notification=disable_notification,
        )


def main() -> None:
    """Главная функция запуска бота."""
    application = build_application()
    logger.info("Огр-маги версии %s заступили на службу", APP_VERSION)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
