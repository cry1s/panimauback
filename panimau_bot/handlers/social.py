from __future__ import annotations

import asyncio
import logging
import random
from typing import cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji, Update
from telegram.ext import ContextTypes

from panimau_bot.constants import REACTION_CHOICES, SOCIAL_PLATFORM_LABELS
from panimau_bot.models import AppServices, PendingDownloadPost
from panimau_bot.services.downloader import extract_download_request
from panimau_bot import voice

logger = logging.getLogger(__name__)


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


def _build_cancel_markup(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(voice.social_cancel_button_text(), callback_data=f"cancel_{message_id}")]]
    )


def _platform_label(platform: str) -> str:
    return SOCIAL_PLATFORM_LABELS.get(platform, "видос")


async def handle_social_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловим ссылки на короткие видео и скачиваем их."""
    message = update.message
    if not message or not message.text:
        return

    services = _get_services(context)
    if message.chat_id != services.settings.group_id:
        return

    request = extract_download_request(message.text.strip())
    if request is None:
        return

    label = _platform_label(request.platform)
    cancel_msg = await message.reply_text(
        voice.render_social_queue(label, services.settings.download_delay_seconds),
        reply_markup=_build_cancel_markup(message.message_id),
    )

    services.pending_store.set(
        str(message.message_id),
        PendingDownloadPost(
            source_msg=message,
            cancel_msg=cancel_msg,
            request=request,
        ),
    )

    context.job_queue.run_once(
        publish_social_video,
        services.settings.download_delay_seconds,
        data={"post_id": str(message.message_id)},
    )


async def publish_social_video(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Качаем и постим social video."""
    services = _get_services(context)
    post_id = str(context.job.data["post_id"])
    post_info = services.pending_store.get(post_id)

    if not isinstance(post_info, PendingDownloadPost):
        return

    label = _platform_label(post_info.request.platform)
    result = None

    try:
        await post_info.cancel_msg.edit_text(voice.render_social_progress(label))
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: services.downloader.download(post_info.request))

        if services.pending_store.get(post_id) is None:
            return

        with result.file_path.open("rb") as video_file:
            channel_msg = await context.bot.send_video(
                services.settings.channel_id,
                video=video_file,
                disable_notification=True,
            )

        with result.file_path.open("rb") as video_file:
            sent_msg = await post_info.source_msg.reply_video(
                video=video_file,
                caption=voice.render_social_reply_caption(
                    label=label,
                    url=result.url,
                    link=channel_msg.link if channel_msg and channel_msg.link else "",
                ),
                disable_notification=True,
            )

        await post_info.cancel_msg.edit_text(voice.render_social_success(label))
        await asyncio.sleep(3)
        await context.bot.set_message_reaction(
            chat_id=sent_msg.chat_id,
            message_id=sent_msg.message_id,
            reaction=[ReactionTypeEmoji(random.choice(REACTION_CHOICES))],
        )
        await post_info.cancel_msg.delete()

        services.stats.add_forward(post_info.request.platform)
    except Exception as exc:
        logger.error("Ошибка при скачивании social video", exc_info=exc)
        await post_info.source_msg.reply_text(
            voice.render_social_error(label, exc),
        )
    finally:
        services.pending_store.pop(post_id, None)
        if result is not None and result.file_path.exists():
            result.file_path.unlink(missing_ok=True)
