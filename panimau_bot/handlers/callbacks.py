from __future__ import annotations

import asyncio
from typing import cast

from telegram import Update
from telegram.ext import ContextTypes

from panimau_bot.models import AppServices
from panimau_bot import voice


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена публикации."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    if not query.data or not query.data.startswith("cancel_"):
        return

    source_msg_id = query.data.removeprefix("cancel_")
    services = _get_services(context)
    post = services.pending_store.pop(source_msg_id, None)

    if post is None or query.message is None:
        return

    await query.message.edit_text(voice.render_post_cancelled())
    services.stats.add_cancel()
    await asyncio.sleep(3)
    await query.message.delete()
