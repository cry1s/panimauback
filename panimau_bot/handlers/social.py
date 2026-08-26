from __future__ import annotations

import asyncio
import logging
import random
import shutil
from typing import cast

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReactionTypeEmoji,
    Update,
)
from telegram.ext import ContextTypes

from panimau_bot.constants import REACTION_CHOICES, SOCIAL_PLATFORM_LABELS
from panimau_bot.models import AppServices, DownloadRequest, PendingDownloadPost
from panimau_bot.services.downloader import extract_download_request
from panimau_bot import voice

logger = logging.getLogger(__name__)

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MEDIA_GROUP_LIMIT = 10


def _get_services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return cast(AppServices, context.application.bot_data["services"])


def _build_cancel_markup(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(voice.social_cancel_button_text(), callback_data=f"cancel_{message_id}")]]
    )


def _platform_label(request: DownloadRequest) -> str:
    if request.platform == "instagram" and "/p/" in request.url:
        return "инста-пост"
    return SOCIAL_PLATFORM_LABELS.get(request.platform, "видос")


def _is_photo(path: object) -> bool:
    suffix = getattr(path, "suffix", "")
    return str(suffix).lower() in PHOTO_SUFFIXES


async def _send_single_file(bot: object, chat_id: object, file_path: object) -> Message:
    sender_name = "send_photo" if _is_photo(file_path) else "send_video"
    media_kwarg = "photo" if _is_photo(file_path) else "video"
    with open(file_path, "rb") as media_file:  # type: ignore[arg-type]
        sender = getattr(bot, sender_name)
        return await sender(chat_id, **{media_kwarg: media_file})


async def _send_media_group(
    bot: object,
    chat_id: object,
    files: list[object],
    caption: str | None = None,
) -> list[Message]:
    handles = []
    try:
        media = []
        for index, file_path in enumerate(files):
            media_file = open(file_path, "rb")  # noqa: SIM115
            handles.append(media_file)
            builder = InputMediaPhoto if _is_photo(file_path) else InputMediaVideo
            item_kwargs: dict[str, object] = {"media": media_file}
            if index == 0 and caption:
                item_kwargs["caption"] = caption
            media.append(builder(**item_kwargs))
        messages = await bot.send_media_group(chat_id, media=media)
        return list(messages)
    finally:
        for handle in handles:
            handle.close()


async def handle_social_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловим ссылки на короткие видео и инста-посты."""
    message = update.message
    if not message or not message.text:
        return

    services = _get_services(context)
    if message.chat_id != services.settings.group_id:
        return

    request = extract_download_request(message.text.strip())
    if request is None:
        return

    label = _platform_label(request)
    cancel_msg = await message.reply_text(
        voice.render_social_queue(label, services.settings.download_delay_seconds),
        reply_markup=_build_cancel_markup(message.message_id),
        disable_notification=True,
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
        publish_social_content,
        services.settings.download_delay_seconds,
        data={"post_id": str(message.message_id)},
    )


async def publish_social_content(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Качаем и постим social контент (видео, фото или альбом)."""
    services = _get_services(context)
    post_id = str(context.job.data["post_id"])
    post_info = services.pending_store.get(post_id)

    if not isinstance(post_info, PendingDownloadPost):
        return

    label = _platform_label(post_info.request)
    result = None

    try:
        await post_info.cancel_msg.edit_text(voice.render_social_progress(label))
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: services.downloader.download(post_info.request))

        if services.pending_store.get(post_id) is None:
            return

        channel_link = ""
        if len(result.file_paths) == 1:
            single_file = result.file_paths[0]
            channel_msg = await _send_single_file(
                context.bot,
                services.settings.channel_id,
                single_file,
            )
            if channel_msg and channel_msg.link:
                channel_link = channel_msg.link

            caption = voice.render_social_reply_caption(
                label=label,
                url=result.url,
                link=channel_link,
            )
            if _is_photo(single_file):
                with open(single_file, "rb") as media_file:
                    sent_msg = await post_info.source_msg.reply_photo(
                        photo=media_file,
                        caption=caption,
                        disable_notification=True,
                    )
            else:
                with open(single_file, "rb") as media_file:
                    sent_msg = await post_info.source_msg.reply_video(
                        video=media_file,
                        caption=caption,
                        disable_notification=True,
                    )
        else:
            chunks = [
                list(result.file_paths[start : start + MEDIA_GROUP_LIMIT])
                for start in range(0, len(result.file_paths), MEDIA_GROUP_LIMIT)
            ]
            first_messages = await _send_media_group(
                context.bot,
                services.settings.channel_id,
                chunks[0],
            )
            for chunk in chunks[1:]:
                await _send_media_group(context.bot, services.settings.channel_id, chunk)

            first_message = first_messages[0] if first_messages else None
            channel_link = first_message.link if first_message and first_message.link else ""
            sent_msg = await post_info.source_msg.reply_text(
                voice.render_social_reply_caption(
                    label=label,
                    url=result.url,
                    link=channel_link,
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

        if services.archive is not None:
            services.archive.register_channel_post(context)

        services.stats.add_forward(post_info.request.platform)
    except Exception as exc:
        logger.error("Ошибка при скачивании social контента", exc_info=exc)
        await post_info.source_msg.reply_text(
            voice.render_social_error(label, exc),
            disable_notification=True,
        )
    finally:
        services.pending_store.pop(post_id, None)
        if result is not None:
            parent_dir: object | None = None
            for file_path in result.file_paths:
                file_path.unlink(missing_ok=True)
                parent_dir = file_path.parent
            if parent_dir is not None:
                shutil.rmtree(parent_dir, ignore_errors=True)
