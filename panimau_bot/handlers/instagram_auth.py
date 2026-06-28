from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from telegram import Message, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes, ConversationHandler

from panimau_bot import voice
from panimau_bot.models import AppServices
from panimau_bot.services.instagram_auth import DEFAULT_INSTAGRAM_TEST_URL, is_instagram_auth_error

logger = logging.getLogger(__name__)

WAITING_AUTH_INPUT, WAITING_PASSWORD, WAITING_TWOFACTOR = range(3)
MAX_COOKIE_FILE_BYTES = 2_000_000
LOGIN_DATA_KEY = "instagram_login"


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


def _is_admin_private(update: Update, services: AppServices) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    return (
        user is not None
        and user.id in services.settings.admin_ids
        and chat is not None
        and chat.type == ChatType.PRIVATE
    )


async def _reply_admin_private_required(update: Update, services: AppServices) -> bool:
    message = update.effective_message
    if _is_admin_private(update, services):
        return True

    if message is None:
        return False

    if update.effective_user is None or update.effective_user.id not in services.settings.admin_ids:
        await message.reply_text(
            voice.render_admin_no_rights(),
            disable_notification=True,
        )
    else:
        await message.reply_text(
            voice.render_admin_private_only(),
            disable_notification=True,
        )
    return False


async def _delete_safely(message: Message | None) -> None:
    if message is None:
        return

    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete sensitive Instagram login message", exc_info=True)


async def ig_login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return ConversationHandler.END

    context.user_data.pop(LOGIN_DATA_KEY, None)
    if update.message:
        await update.message.reply_text(voice.render_instagram_login_intro())
    return WAITING_AUTH_INPUT


async def ig_login_cookie_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return ConversationHandler.END

    message = update.message
    document = message.document if message and message.document else None
    if document is None:
        return WAITING_AUTH_INPUT

    if document.file_size and document.file_size > MAX_COOKIE_FILE_BYTES:
        await message.reply_text(voice.render_instagram_cookie_error("file is too large"))
        return WAITING_AUTH_INPUT

    try:
        telegram_file = await document.get_file()
        raw_bytes = bytes(await telegram_file.download_as_bytearray())
        services.instagram_auth.save_cookie_bytes(raw_bytes)
    except Exception as exc:
        await message.reply_text(voice.render_instagram_cookie_error(exc))
        return WAITING_AUTH_INPUT

    await message.reply_text(voice.render_instagram_cookie_saved())
    context.user_data.pop(LOGIN_DATA_KEY, None)
    return ConversationHandler.END


async def ig_login_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return ConversationHandler.END

    message = update.message
    username = message.text.strip() if message and message.text else ""
    if not username:
        return WAITING_AUTH_INPUT

    context.user_data[LOGIN_DATA_KEY] = {"username": username}
    await message.reply_text(voice.render_instagram_login_ask_password(username))
    return WAITING_PASSWORD


async def ig_login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return ConversationHandler.END

    message = update.message
    password = message.text if message and message.text else ""
    if not password:
        return WAITING_PASSWORD

    login_data = cast(dict[str, Any], context.user_data.setdefault(LOGIN_DATA_KEY, {}))
    login_data["password"] = password
    await _delete_safely(message)

    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=voice.render_instagram_login_ask_twofactor(),
        )
    return WAITING_TWOFACTOR


async def ig_login_twofactor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return ConversationHandler.END

    message = update.message
    twofactor = message.text.strip() if message and message.text else ""
    await _delete_safely(message)

    login_data = cast(dict[str, Any], context.user_data.get(LOGIN_DATA_KEY, {}))
    username = str(login_data.get("username", "")).strip()
    password = str(login_data.get("password", ""))
    clean_twofactor = None if twofactor in {"", "-", "/skip"} else twofactor

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: services.instagram_auth.verify_credentials(
                username=username,
                password=password,
                twofactor=clean_twofactor,
            ),
        )
    except Exception as exc:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=voice.render_instagram_login_failed(exc),
            )
    else:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=voice.render_instagram_login_success(result),
            )
    finally:
        context.user_data.pop(LOGIN_DATA_KEY, None)

    return ConversationHandler.END


async def ig_login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop(LOGIN_DATA_KEY, None)
    if update.message:
        await update.message.reply_text(voice.render_instagram_login_cancelled())
    return ConversationHandler.END


async def ig_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return

    if update.message:
        await update.message.reply_text(voice.render_instagram_status(services.instagram_auth.status()))


async def ig_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return

    deleted = services.instagram_auth.logout()
    if update.message:
        await update.message.reply_text(voice.render_instagram_logout(deleted))


async def ig_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _get_services(context)
    if not await _reply_admin_private_required(update, services):
        return

    message = update.message
    if message is None:
        return

    url = context.args[0] if context.args else DEFAULT_INSTAGRAM_TEST_URL
    progress_message = await message.reply_text(voice.render_instagram_test_started(url))

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: services.instagram_auth.test_url(url))
    except Exception as exc:
        text = voice.render_social_auth_required("рилс") if is_instagram_auth_error(exc) else voice.render_instagram_test_error(exc)
        await progress_message.edit_text(text)
        return

    await progress_message.edit_text(voice.render_instagram_test_success(result))
