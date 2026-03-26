from __future__ import annotations

import asyncio
import logging
from typing import cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, filters

from panimau_bot.models import AppServices, AttachmentItem, PendingAttachmentPost
from panimau_bot import voice

logger = logging.getLogger(__name__)

ATTACHMENT_FILTER = (
    filters.PHOTO
    | filters.VIDEO
    | filters.AUDIO
    | filters.Document.ALL
    | filters.VOICE
    | filters.ANIMATION
)

ATTACHMENT_SENDERS = {
    "photo": "send_photo",
    "video": "send_video",
    "audio": "send_audio",
    "voice": "send_voice",
    "document": "send_document",
    "animation": "send_animation",
    "sticker": "send_sticker",
}


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


def _build_cancel_markup(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(voice.attachment_cancel_button_text(), callback_data=f"cancel_{message_id}")]]
    )


def _collect_attachment_items(message: Message) -> list[AttachmentItem]:
    items: list[AttachmentItem] = []

    if message.photo:
        items.append(("photo", message.photo[-1].file_id))
    if message.video:
        items.append(("video", message.video.file_id))
    if message.audio:
        items.append(("audio", message.audio.file_id))
    if message.voice:
        items.append(("voice", message.voice.file_id))
    if message.document:
        items.append(("document", message.document.file_id))
    if message.animation:
        items.append(("animation", message.animation.file_id))
    if message.sticker:
        items.append(("sticker", message.sticker.file_id))

    return items


async def handle_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка всех вложений из группы."""
    message = update.message
    if not message:
        return

    services = _get_services(context)
    if message.chat_id != services.settings.group_id:
        return

    file_types = _collect_attachment_items(message)
    if not file_types:
        return

    cancel_msg = await message.reply_text(
        voice.render_attachment_queue(services.settings.download_delay_seconds),
        reply_markup=_build_cancel_markup(message.message_id),
    )

    services.pending_store.set(
        str(message.message_id),
        PendingAttachmentPost(
            source_msg=message,
            cancel_msg=cancel_msg,
            file_types=file_types,
        ),
    )

    context.job_queue.run_once(
        publish_post,
        services.settings.download_delay_seconds,
        data={"post_id": str(message.message_id)},
    )


async def publish_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Публикация вложений после таймаута."""
    services = _get_services(context)
    post_id = str(context.job.data["post_id"])
    post_info = services.pending_store.get(post_id)

    if not isinstance(post_info, PendingAttachmentPost):
        return

    try:
        for file_type, file_id in post_info.file_types:
            sender_name = ATTACHMENT_SENDERS[file_type]
            sender = getattr(context.bot, sender_name)
            await sender(
                services.settings.channel_id,
                file_id,
                disable_notification=True,
            )

        await post_info.cancel_msg.edit_text(voice.render_attachment_success())
        await asyncio.sleep(2)
        await post_info.cancel_msg.delete()

        for file_type, _ in post_info.file_types:
            services.stats.add_forward(file_type)
    except Exception as exc:
        logger.error("Ошибка при публикации вложения", exc_info=exc)
        await post_info.source_msg.reply_text(voice.render_attachment_publish_error(exc))
    finally:
        services.pending_store.pop(post_id, None)
