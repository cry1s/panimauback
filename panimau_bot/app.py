from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from panimau_bot.config import Settings
from panimau_bot.constants import SOCIAL_URL_FILTER_PATTERN
from panimau_bot.handlers.attachments import ATTACHMENT_FILTER, handle_attachment
from panimau_bot.handlers.callbacks import handle_cancel
from panimau_bot.handlers.commands import admin_broadcast, health_check, show_stats, start, tell_joke
from panimau_bot.handlers.instagram_auth import (
    WAITING_AUTH_INPUT,
    WAITING_PASSWORD,
    WAITING_TWOFACTOR,
    ig_login_cancel,
    ig_login_cookie_document,
    ig_login_password,
    ig_login_start,
    ig_login_twofactor,
    ig_login_username,
    ig_logout,
    ig_status,
    ig_test,
)
from panimau_bot.handlers.social import handle_social_link
from panimau_bot.models import AppServices, PendingStore
from panimau_bot.services.downloader import SocialVideoDownloader
from panimau_bot.services.instagram_auth import InstagramAuthService
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
    app_settings.state_dir.mkdir(parents=True, exist_ok=True)
    application = Application.builder().token(app_settings.bot_token).build()
    downloader = SocialVideoDownloader(cookiefile=app_settings.instagram_cookies_file)

    application.bot_data["services"] = AppServices(
        settings=app_settings,
        stats=BotStats(),
        pending_store=PendingStore(),
        downloader=downloader,
        instagram_auth=InstagramAuthService(app_settings.instagram_cookies_file, downloader),
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("joke", tell_joke))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("ig_login", ig_login_start)],
            states={
                WAITING_AUTH_INPUT: [
                    MessageHandler(filters.Document.ALL, ig_login_cookie_document),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, ig_login_username),
                ],
                WAITING_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, ig_login_password),
                ],
                WAITING_TWOFACTOR: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, ig_login_twofactor),
                ],
            },
            fallbacks=[CommandHandler("cancel", ig_login_cancel)],
            conversation_timeout=300,
        )
    )
    application.add_handler(CommandHandler("ig_status", ig_status))
    application.add_handler(CommandHandler("ig_test", ig_test))
    application.add_handler(CommandHandler("ig_logout", ig_logout))
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
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
