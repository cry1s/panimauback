from __future__ import annotations

import random
from typing import cast

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from panimau_bot.models import AppServices
from panimau_bot.release import APP_VERSION, CHANGELOG
from panimau_bot import voice


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


def _silent_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False

    services = _get_services(context)
    return chat.id == services.settings.group_id


def _is_admin(update: Update, services: AppServices) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id in services.settings.admin_ids
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start и /help."""
    if update.message:
        await update.message.reply_text(
            voice.render_welcome(),
            disable_notification=_silent_in_group(update, context),
        )


def _archive_progress(services: AppServices) -> tuple[int, int] | None:
    if services.archive is not None and services.archive.enabled:
        return services.archive.progress
    return None


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда проверки здоровья бота."""
    services = _get_services(context)
    uptime = services.stats.get_uptime()
    joke = voice.pick_joke() if random.random() < 0.3 else None
    response = voice.render_health(
        uptime=uptime,
        total_forwarded=services.stats.total_forwarded,
        cancelled=services.stats.cancelled,
        joke=joke,
        archive_progress=_archive_progress(services),
    )

    if update.message:
        await update.message.reply_text(
            response,
            disable_notification=_silent_in_group(update, context),
        )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику работы бота."""
    services = _get_services(context)
    stats = services.stats

    if not stats.total_attempts:
        if update.message:
            await update.message.reply_text(
                voice.render_empty_stats(),
                disable_notification=_silent_in_group(update, context),
            )
        return

    if update.message:
        await update.message.reply_text(
            voice.render_stats(stats, archive_progress=_archive_progress(services)),
            parse_mode=ParseMode.MARKDOWN,
            disable_notification=_silent_in_group(update, context),
        )


async def tell_joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Рассказать анекдот."""
    if update.message:
        await update.message.reply_text(
            voice.render_tell_joke(),
            disable_notification=_silent_in_group(update, context),
        )


async def show_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать текущую версию и список изменений."""
    if update.message:
        await update.message.reply_text(
            voice.render_version(APP_VERSION, CHANGELOG),
            disable_notification=_silent_in_group(update, context),
        )


async def submit_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохранить жалобу или предложение."""
    services = _get_services(context)
    message = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat:
        return

    feedback_text = " ".join(context.args).strip()
    if not feedback_text:
        await message.reply_text(
            voice.render_feedback_missing(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    try:
        feedback_id = services.state.add_feedback(
            text=feedback_text,
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            chat_id=chat.id,
            chat_type=chat.type,
            message_id=message.message_id,
            bot_version=APP_VERSION,
        )
        await message.reply_text(
            voice.render_feedback_saved(feedback_id),
            disable_notification=_silent_in_group(update, context),
        )
    except Exception as exc:
        await message.reply_text(
            voice.render_feedback_error(exc),
            disable_notification=_silent_in_group(update, context),
        )


async def export_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выгрузить журнал обращений администратору."""
    services = _get_services(context)
    message = update.message
    if not message:
        return

    if not _is_admin(update, services):
        await message.reply_text(
            voice.render_admin_no_rights(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    if message.chat.type != ChatType.PRIVATE:
        await message.reply_text(
            voice.render_admin_private_only(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    if not services.state.has_feedback():
        await message.reply_text(voice.render_feedback_empty())
        return

    try:
        with services.state.feedback_file.open("rb") as feedback_file:
            await message.reply_document(
                document=feedback_file,
                filename=f"feedback-{APP_VERSION}.jsonl",
                caption=voice.render_feedback_export_caption(),
            )
    except Exception as exc:
        await message.reply_text(voice.render_feedback_error(exc))


async def vk_diagnostic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Секретный код 112: досмотр ключа от старых кладовых."""
    services = _get_services(context)
    message = update.message

    if not message:
        return

    if not _is_admin(update, services):
        await message.reply_text(
            voice.render_admin_no_rights(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    if not services.archive or not services.settings.vk_service_token:
        await message.reply_text(
            voice.render_vk_diagnostic_no_token(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    try:
        result = await asyncio.to_thread(services.archive.client.diagnose)
    except Exception as exc:
        await message.reply_text(
            voice.render_vk_diagnostic_error(str(exc)),
            disable_notification=_silent_in_group(update, context),
        )
        return

    if result.get("ok"):
        await message.reply_text(
            voice.render_vk_diagnostic_ok(
                group_name=str(result.get("group_name", "")),
                group_id=int(result.get("group_id") or 0),
            ),
            disable_notification=_silent_in_group(update, context),
        )
        return

    await message.reply_text(
        voice.render_vk_diagnostic_error(str(result.get("error", "неизвестная причина"))),
        disable_notification=_silent_in_group(update, context),
    )


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для админов - вброс в канал."""
    services = _get_services(context)
    message = update.message

    if not message:
        return

    if not _is_admin(update, services):
        await message.reply_text(
            voice.render_admin_no_rights(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    if not context.args:
        await message.reply_text(
            voice.render_admin_missing_args(),
            disable_notification=_silent_in_group(update, context),
        )
        return

    text = " ".join(context.args)
    try:
        await context.bot.send_message(
            services.settings.channel_id,
            text,
            parse_mode=ParseMode.MARKDOWN,
        )
        await message.reply_text(
            voice.render_admin_success(),
            disable_notification=_silent_in_group(update, context),
        )
    except Exception as exc:
        await message.reply_text(
            voice.render_admin_error(exc),
            disable_notification=_silent_in_group(update, context),
        )
