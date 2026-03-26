from __future__ import annotations

import random
from typing import cast

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from panimau_bot.models import AppServices
from panimau_bot import voice


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start и /help."""
    if update.message:
        await update.message.reply_text(voice.render_welcome())


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
    )

    if update.message:
        await update.message.reply_text(response)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику работы бота."""
    services = _get_services(context)
    stats = services.stats

    if not stats.total_attempts:
        if update.message:
            await update.message.reply_text(voice.render_empty_stats())
        return

    if update.message:
        await update.message.reply_text(voice.render_stats(stats), parse_mode=ParseMode.MARKDOWN)


async def tell_joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Рассказать анекдот."""
    if update.message:
        await update.message.reply_text(voice.render_tell_joke())


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для админов - вброс в канал."""
    services = _get_services(context)
    message = update.message

    if not message:
        return

    if update.effective_user is None or update.effective_user.id not in services.settings.admin_ids:
        await message.reply_text(voice.render_admin_no_rights())
        return

    if not context.args:
        await message.reply_text(voice.render_admin_missing_args())
        return

    text = " ".join(context.args)
    try:
        await context.bot.send_message(
            services.settings.channel_id,
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_notification=True,
        )
        await message.reply_text(voice.render_admin_success())
    except Exception as exc:
        await message.reply_text(voice.render_admin_error(exc))
