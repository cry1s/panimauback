from __future__ import annotations

import logging

from telegram import Update
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
from panimau_bot.handlers.commands import admin_broadcast, health_check, show_stats, start, tell_joke
from panimau_bot.handlers.social import handle_social_link
from panimau_bot.models import AppServices, PendingStore
from panimau_bot.services.downloader import SocialVideoDownloader
from panimau_bot.stats import BotStats
from panimau_bot import voice

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application(settings: Settings | None = None) -> Application:
    """Создаёт и настраивает приложение бота."""
    app_settings = settings or Settings.from_env()
    application = Application.builder().token(app_settings.bot_token).build()

    application.bot_data["services"] = AppServices(
        settings=app_settings,
        stats=BotStats(),
        pending_store=PendingStore(),
        downloader=SocialVideoDownloader(cookiefile=app_settings.ytdlp_cookies_file),
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("joke", tell_joke))
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
        await update.effective_message.reply_text(voice.render_general_error())


def main() -> None:
    """Главная функция запуска бота."""
    application = build_application()
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
