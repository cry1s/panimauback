from __future__ import annotations

import asyncio
import logging
import random
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests
from telegram import InputMediaAudio, InputMediaPhoto, InputMediaVideo

from panimau_bot.services.state import BotState

if TYPE_CHECKING:
    from panimau_bot.config import Settings

logger = logging.getLogger(__name__)


class MediaUnavailableError(Exception):
    """Медиа поста недоступно для скачивания — пост целиком пропускаем."""


VK_API_URL = "https://api.vk.com/method/{method}"
VK_API_VERSION = "5.199"
REQUEST_TIMEOUT = 30

MAX_MEDIA_PER_POST = 10
CAPTION_LIMIT_MEDIA = 1024
CAPTION_LIMIT_TEXT = 4096

PHOTO_FALLBACK_KEYS = ("photo_2560", "photo_1280", "photo_807", "photo_604")
VIDEO_FILE_KEYS = ("mp4_1080", "mp4_720", "mp4_480", "mp4_360", "mp4_240")


@dataclass(slots=True)
class VkVideoAttachment:
    owner_id: int
    video_id: int
    title: str = ""
    access_key: str | None = None
    file_url: str | None = None

    @property
    def page_url(self) -> str:
        base = f"https://vk.com/video{self.owner_id}_{self.video_id}"
        if self.access_key:
            return f"{base}_{self.access_key}"
        return base


@dataclass(slots=True)
class VkAudioAttachment:
    artist: str = ""
    title: str = ""
    url: str | None = None

    @property
    def label(self) -> str:
        parts = [part for part in (self.artist.strip(), self.title.strip()) if part]
        return " — ".join(parts) if parts else "трек"


@dataclass(slots=True)
class VkAttachments:
    photo_urls: tuple[str, ...] = ()
    videos: tuple[VkVideoAttachment, ...] = ()
    audios: tuple[VkAudioAttachment, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.photo_urls and not self.videos and not self.audios


@dataclass(slots=True)
class VkRepost:
    author: str
    text: str
    attachments: VkAttachments = field(default_factory=VkAttachments)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and self.attachments.is_empty


@dataclass(slots=True)
class VkPost:
    post_id: int
    text: str
    attachments: VkAttachments
    repost: VkRepost | None = None

    @property
    def is_empty(self) -> bool:
        if self.text.strip() or not self.attachments.is_empty:
            return False
        return self.repost is None or self.repost.is_empty


def build_post_caption(post: VkPost, limit: int = CAPTION_LIMIT_TEXT) -> str:
    """Собираем текст поста вместе с репостом. Без ссылок на недостающее медиа."""
    parts: list[str] = []
    if post.text.strip():
        parts.append(post.text.strip())

    if post.repost is not None and not post.repost.is_empty:
        header = f"↪ {post.repost.author}:" if post.repost.author else "↪ из чужой ленты:"
        block_parts = [header]
        if post.repost.text.strip():
            block_parts.append(post.repost.text.strip())
        parts.append("\n".join(part for part in block_parts if part))

    caption = "\n\n".join(part for part in parts if part).strip()
    if len(caption) > limit:
        caption = caption[: limit - 1].rstrip() + "…"
    return caption


def post_has_unresolved_media(post: VkPost) -> bool:
    """Пост содержит видео/аудио, которое нельзя скачать файлом — пост целиком скипаем."""
    sources = [post.attachments]
    if post.repost is not None:
        sources.append(post.repost.attachments)
    for source in sources:
        for video in source.videos:
            if video.file_url is None:
                return True
        for audio in source.audios:
            if audio.url is None:
                return True
    return False


def collect_visual_media(
    post: VkPost,
) -> tuple[tuple[str, ...], tuple[VkVideoAttachment, ...]]:
    """Фото и скачабельные видео из поста и репоста, одним альбомом без повторов."""
    photos: list[str] = []
    videos: list[VkVideoAttachment] = []
    seen_videos: set[tuple[int, int]] = set()

    sources = [post.attachments]
    if post.repost is not None:
        sources.append(post.repost.attachments)

    for source in sources:
        for url in source.photo_urls:
            if len(photos) + len(videos) >= MAX_MEDIA_PER_POST:
                break
            if url not in photos:
                photos.append(url)
        for video in source.videos:
            if len(photos) + len(videos) >= MAX_MEDIA_PER_POST:
                break
            key = (video.owner_id, video.video_id)
            if video.file_url and key not in seen_videos:
                seen_videos.add(key)
                videos.append(video)

    return tuple(photos), tuple(videos)


def collect_audios(post: VkPost) -> tuple[VkAudioAttachment, ...]:
    """Треки из поста и репоста с прямыми ссылками, без повторов."""
    audios: list[VkAudioAttachment] = []
    seen: set[str] = set()

    sources = [post.attachments]
    if post.repost is not None:
        sources.append(post.repost.attachments)

    for source in sources:
        for audio in source.audios:
            if audio.url is None:
                continue
            label = audio.label
            if label not in seen:
                seen.add(label)
                audios.append(audio)

    return tuple(audios[:MAX_MEDIA_PER_POST])


class VkWallClient:
    """Минимальный клиент стены VK без внешних зависимостей."""

    def __init__(self, service_token: str, source_domain: str) -> None:
        self.service_token = service_token
        self.source_domain = source_domain
        self._group_id: int | None = None
        self._name_cache: dict[int, str] = {}
        self._video_file_cache: dict[str, str | None] = {}

    def _call(self, method: str, **params: Any) -> Any:
        response = requests.post(
            VK_API_URL.format(method=method),
            data={
                **params,
                "access_token": self.service_token,
                "v": VK_API_VERSION,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            message = payload["error"].get("error_msg", "unknown error")
            raise RuntimeError(f"VK API {method}: {message}")
        return payload["response"]

    @staticmethod
    def _unwrap_items(response: Any, key: str) -> list[dict[str, Any]]:
        if isinstance(response, dict):
            value = response.get(key, [])
        elif isinstance(response, list):
            value = response
        else:
            value = []
        return [item for item in value if isinstance(item, dict)]

    def group_id(self) -> int:
        if self._group_id is None:
            response = self._call("groups.getById", group_id=self.source_domain, fields="name")
            groups = self._unwrap_items(response, "groups")
            if not groups:
                raise RuntimeError(f"VK API: не нашли сообщество {self.source_domain}")
            self._group_id = int(groups[0]["id"])
            self._name_cache[self._group_id] = str(groups[0].get("name", ""))
        return self._group_id

    @staticmethod
    def best_photo_url(photo: dict[str, Any]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for size in photo.get("sizes") or []:
            url = size.get("url")
            if url:
                area = int(size.get("width") or 0) * int(size.get("height") or 0)
                candidates.append((area, url))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        for key in PHOTO_FALLBACK_KEYS:
            if photo.get(key):
                return photo[key]
        return None

    def diagnose(self) -> dict[str, object]:
        """Секретный досмотр: валиден ли токен и открывается ли источник."""
        result: dict[str, object] = {"ok": False}

        try:
            self._call("users.get")
        except Exception as exc:
            result["error"] = f"токен не прошёл досмотр: {exc}"
            return result

        try:
            group_id = self.group_id()
        except Exception as exc:
            result["error"] = f"старые кладовые не открылись: {exc}"
            return result

        try:
            wall = self._call(
                "wall.get",
                owner_id=-group_id,
                offset=0,
                count=1,
                filter="owner",
            )
            total = int((wall or {}).get("count") or 0) if isinstance(wall, dict) else 0
        except Exception as exc:
            result["error"] = f"стена недоступна для чтения: {exc}"
            return result

        result["ok"] = True
        result["group_name"] = self._name_cache.get(group_id, "")
        result["group_id"] = group_id
        result["wall_posts"] = total
        return result

    def resolve_video_file(self, video: dict[str, Any]) -> str | None:
        owner_id = int(video.get("owner_id") or 0)
        video_id = int(video.get("id") or 0)
        access_key = video.get("access_key")
        cache_key = f"{owner_id}_{video_id}_{access_key or ''}"
        if cache_key in self._video_file_cache:
            return self._video_file_cache[cache_key]

        file_url: str | None = None
        try:
            target = f"{owner_id}_{video_id}" + (f"_{access_key}" if access_key else "")
            response = self._call("video.get", videos=target, count=1)
            items = self._unwrap_items(response, "items")
            files = items[0].get("files") if items else None
            if isinstance(files, dict):
                for key in VIDEO_FILE_KEYS:
                    if files.get(key):
                        file_url = files[key]
                        break
        except Exception:
            logger.warning("Не удалось раскрыть видео %s_%s", owner_id, video_id, exc_info=True)

        self._video_file_cache[cache_key] = file_url
        return file_url

    def build_attachments(self, attachments: Any) -> VkAttachments:
        photo_urls: list[str] = []
        videos: list[VkVideoAttachment] = []
        audios: list[VkAudioAttachment] = []

        for attachment in attachments or []:
            if not isinstance(attachment, dict):
                continue
            kind = attachment.get("type")

            if kind == "photo" and isinstance(attachment.get("photo"), dict):
                url = self.best_photo_url(attachment["photo"])
                if url:
                    photo_urls.append(url)

            elif kind == "video":
                raw_video = attachment.get("video")
                if not isinstance(raw_video, dict):
                    continue
                video = VkVideoAttachment(
                    owner_id=int(raw_video.get("owner_id") or 0),
                    video_id=int(raw_video.get("id") or 0),
                    title=(raw_video.get("title") or "").strip(),
                    access_key=raw_video.get("access_key"),
                )
                video.file_url = (
                    self.resolve_video_file(raw_video)
                    if video.owner_id and video.video_id
                    else None
                )
                videos.append(video)

            elif kind == "audio" and isinstance(attachment.get("audio"), dict):
                raw_audio = attachment["audio"]
                audios.append(
                    VkAudioAttachment(
                        artist=str(raw_audio.get("artist") or "").strip(),
                        title=str(raw_audio.get("title") or "").strip(),
                        url=raw_audio.get("url") or None,
                    )
                )

        return VkAttachments(photo_urls=tuple(photo_urls), videos=tuple(videos), audios=tuple(audios))

    def resolve_author(self, from_id: int | None) -> str:
        if not from_id:
            return ""
        if from_id in self._name_cache:
            return self._name_cache[from_id]

        name = ""
        try:
            if from_id > 0:
                response = self._call("users.get", user_ids=from_id)
                users = self._unwrap_items(response, "users")
                if users:
                    name = f"{users[0].get('first_name', '')} {users[0].get('last_name', '')}".strip()
            else:
                response = self._call("groups.getById", group_id=-from_id, fields="name")
                groups = self._unwrap_items(response, "groups")
                if groups:
                    name = str(groups[0].get("name", "")).strip()
        except Exception:
            logger.warning("Не удалось узнать автора для %s", from_id, exc_info=True)

        name = name or "автор неизвестен"
        self._name_cache[from_id] = name
        return name

    def build_post(self, item: dict[str, Any]) -> VkPost:
        repost: VkRepost | None = None
        history = item.get("copy_history") or []
        origin = next((entry for entry in history if isinstance(entry, dict)), None)
        if origin is not None:
            repost = VkRepost(
                author=self.resolve_author(origin.get("from_id")),
                text=(origin.get("text") or "").strip(),
                attachments=self.build_attachments(origin.get("attachments")),
            )

        return VkPost(
            post_id=int(item.get("id") or 0),
            text=(item.get("text") or "").strip(),
            attachments=self.build_attachments(item.get("attachments")),
            repost=repost,
        )

    def fetch_all_post_ids(self) -> list[int]:
        group_id = self.group_id()
        ids: list[int] = []
        offset = 0
        total: int | None = None

        while total is None or offset < total:
            response = self._call(
                "wall.get",
                owner_id=-group_id,
                offset=offset,
                count=100,
                filter="owner",
            )
            items = response.get("items", []) if isinstance(response, dict) else []
            total = int((response or {}).get("count") or 0) if isinstance(response, dict) else 0
            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("is_pinned") or item.get("marked_as_ads"):
                    continue
                post_id = item.get("id")
                if isinstance(post_id, int):
                    ids.append(post_id)

            offset += len(items)

        return ids

    def fetch_post(self, post_id: int) -> VkPost | None:
        group_id = self.group_id()
        response = self._call("wall.getById", posts=f"-{group_id}_{post_id}")
        items = response.get("items", []) if isinstance(response, dict) else response
        if not items:
            return None
        first = items[0]
        return self.build_post(first) if isinstance(first, dict) else None


class ArchiveRepublisher:
    """Тайные закрома: копим публикации канала, вспоминаем старые запасы."""

    def __init__(self, settings: "Settings", state: BotState, client: VkWallClient | None = None) -> None:
        self.settings = settings
        self.state = state
        self.client = client or VkWallClient(settings.vk_service_token, settings.vk_source_domain)
        self._queue: list[int] = []
        self._published: list[int] = []
        self._total = 0
        self._counter = 0
        self._scheduled_at: str | None = None
        self._ensure_scheduled = False
        self._load()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.vk_service_token)

    @property
    def progress(self) -> tuple[int, int]:
        return len(self._published), self._total

    def has_pending(self) -> bool:
        return bool(self._queue)

    # --- состояние -------------------------------------------------------

    def _load(self) -> None:
        payload = self.state.read_archive_state()
        self._queue = [int(item) for item in payload.get("queue", [])]
        self._published = [int(item) for item in payload.get("published", [])]
        self._total = int(payload.get("total") or 0)
        self._counter = int(payload.get("counter") or 0)
        scheduled_at = payload.get("scheduled_at")
        self._scheduled_at = str(scheduled_at) if scheduled_at else None

    def _save(self) -> None:
        self.state.write_archive_state(
            {
                "total": self._total,
                "queue": self._queue,
                "published": self._published,
                "counter": self._counter,
                "scheduled_at": self._scheduled_at,
            }
        )

    # --- очередь ---------------------------------------------------------

    def ensure_queue(self) -> None:
        """Единожды собираем список запасов в случайном порядке."""
        if self._total or self._queue:
            return

        already_seen = set(self._published)
        ids = [post_id for post_id in self.client.fetch_all_post_ids() if post_id not in already_seen]
        random.shuffle(ids)
        self._queue = ids
        self._total = len(ids) + len(self._published)
        self._save()

    def _ensure_queue_later(self, context: Any) -> None:
        """Очередь ещё пуста — дозаряжаем её в фоне, чтобы дрип не молчал навсегда."""
        if self._ensure_scheduled:
            return
        self._ensure_scheduled = True
        if context.job_queue is not None:
            context.job_queue.run_once(ensure_queue_job, 5)
        logger.warning("Закрома ещё пусты — отложили сбор очереди в фоне.")

    # --- планирование ----------------------------------------------------

    def register_channel_post(self, context: Any) -> None:
        """Каждый N-й пост канала будит одну из забытых кладовых."""
        if not self.enabled:
            return

        if not self._total:
            self._ensure_queue_later(context)
            return

        if self._scheduled_at:
            return

        self._counter += 1
        trigger = max(1, int(self.settings.archive_trigger_posts))
        if self._counter < trigger:
            self._save()
            return

        self._counter = 0
        min_delay = max(0, int(self.settings.archive_min_delay_seconds))
        max_delay = max(min_delay, int(self.settings.archive_max_delay_seconds))
        delay = float(random.uniform(min_delay, max_delay))

        scheduled_at = datetime.now(UTC) + timedelta(seconds=delay)
        self._scheduled_at = scheduled_at.isoformat()
        self._save()

        if context.job_queue is not None:
            context.job_queue.run_once(publish_scheduled_post, delay)
            logger.info("Закрома зашевелились, следующая поставка через %.0f сек.", delay)

    def resume_pending_schedule(self) -> float | None:
        """После перезапуска вспоминаем отложенную поставку."""
        if not self.enabled or not self._scheduled_at or not self._queue:
            return None

        try:
            scheduled_at = datetime.fromisoformat(self._scheduled_at)
        except ValueError:
            self._scheduled_at = None
            self._save()
            return None

        delay = (scheduled_at - datetime.now(UTC)).total_seconds()
        return max(delay, 5.0)

    # --- публикация ------------------------------------------------------

    async def publish_scheduled(self, context: Any, schedule_next: bool = True) -> None:
        """Тянем один пост из запасов и выкладываем целиком."""
        self._scheduled_at = None

        if not self.enabled or not self._queue:
            self._save()
            return

        post_id = self._queue.pop(0)
        loop = asyncio.get_running_loop()

        try:
            post = await loop.run_in_executor(None, self.client.fetch_post, post_id)
        except Exception:
            logger.exception("Не удалось вытащить запас %s", post_id)
            self._queue.append(post_id)
            self._save()
            return

        if post is None or post.is_empty:
            self._mark_published(post_id)
            return

        if post_has_unresolved_media(post):
            logger.info("Закрома: пост %s пропущен — медиа недоступно для скачивания.", post_id)
            self._mark_published(post_id)
            return

        caption = build_post_caption(post)
        photos, videos = collect_visual_media(post)
        audios = collect_audios(post)

        try:
            visual_files, audio_files = await loop.run_in_executor(
                None, self._download_media, photos, videos, audios
            )

            for chat_id in (self.settings.channel_id, self.settings.group_id):
                await self._deliver_to(context, chat_id, caption, visual_files, audio_files)

            logger.info("Закрома: пост %s разошёлся по каналу и беседе.", post_id)
        except MediaUnavailableError as exc:
            logger.warning("Закрома: пост %s пропущен — %s", post_id, exc)
            self._mark_published(post_id)
            return
        except Exception as exc:
            logger.exception("Запас %s не прошел в канал: (%s)", post_id, exc)
            self._queue.append(post_id)
            self._save()
            return

        self._mark_published(post_id)

        if schedule_next and context.job_queue is not None:
            self.register_channel_post(context)

    def _mark_published(self, post_id: int) -> None:
        self._published.append(post_id)
        done, total = self.progress
        logger.info("Закрома: разобрано %s из %s.", done, total)
        self._save()

    async def _deliver_to(
        self,
        context: Any,
        chat_id: object,
        caption: str,
        visual_files: list[Path],
        audio_files: list[Path],
    ) -> None:
        if not visual_files and not audio_files:
            await context.bot.send_message(chat_id, caption)
            return

        caption_fits_media = len(caption) <= CAPTION_LIMIT_MEDIA

        if not caption_fits_media:
            await context.bot.send_message(chat_id, caption)

        group_caption = caption if caption_fits_media else None
        if visual_files:
            await self._send_grouped(context, chat_id, visual_files, group_caption)
        if audio_files:
            audio_caption = group_caption if not visual_files else None
            await self._send_grouped(context, chat_id, audio_files, audio_caption)

    async def _send_grouped(
        self, context: Any, chat_id: object, files: list[Path], caption: str | None
    ) -> None:
        handles = []
        try:
            media = []
            for index, file_path in enumerate(files):
                handle = file_path.open("rb")
                handles.append(handle)
                suffix = file_path.suffix.lower()
                if suffix == ".mp4":
                    builder = InputMediaVideo
                elif suffix == ".mp3":
                    builder = InputMediaAudio
                else:
                    builder = InputMediaPhoto
                item_kwargs: dict[str, object] = {"media": handle}
                if index == 0 and caption:
                    item_kwargs["caption"] = caption
                media.append(builder(**item_kwargs))

            for start in range(0, len(media), MAX_MEDIA_PER_POST):
                chunk = media[start : start + MAX_MEDIA_PER_POST]
                await context.bot.send_media_group(chat_id, media=chunk)
        finally:
            for handle in handles:
                handle.close()

    def _download_media(
        self,
        photo_urls: tuple[str, ...],
        videos: tuple[VkVideoAttachment, ...],
        audios: tuple[VkAudioAttachment, ...],
    ) -> tuple[list[Path], list[Path]]:
        output_dir = Path(tempfile.gettempdir()) / f"panimau_archive_{int(time.time() * 1000)}"
        output_dir.mkdir(parents=True, exist_ok=True)

        visual_files: list[Path] = []
        audio_files: list[Path] = []

        for index, url in enumerate(photo_urls):
            target = self._fetch_to(output_dir / f"item_{index:02d}.jpg", url)
            if target is not None:
                visual_files.append(target)

        for index, video in enumerate(videos):
            target = self._fetch_to(output_dir / f"clip_{index:02d}.mp4", video.file_url or "")
            if target is not None:
                visual_files.append(target)
            else:
                raise MediaUnavailableError(f"видео не скачалось: {video.page_url}")

        for index, audio in enumerate(audios):
            target = self._fetch_to(output_dir / f"track_{index:02d}.mp3", audio.url or "")
            if target is not None:
                audio_files.append(target)
            else:
                raise MediaUnavailableError(f"трек не скачался: {audio.label}")

        return visual_files, audio_files

    def _fetch_to(self, target: Path, url: str) -> Path | None:
        if not url:
            return None
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            target.write_bytes(response.content)
            return target
        except Exception:
            logger.warning("Файл не скачался: %s", url, exc_info=True)
            return None


async def publish_scheduled_post(context: Any) -> None:
    """Точка входа для JobQueue."""
    services = context.application.bot_data.get("services")
    archive = getattr(services, "archive", None)
    if archive is None:
        return
    await archive.publish_scheduled(context)


async def ensure_queue_job(context: Any) -> None:
    """Собираем очередь кладовых, повторяя попытку, пока не выйдет."""
    services = context.application.bot_data.get("services")
    archive = getattr(services, "archive", None)
    if archive is None or not archive.enabled:
        return

    try:
        await asyncio.to_thread(archive.ensure_queue)
    except Exception:
        logger.warning("Не удалось собрать старые кладовые, повторим позже")
        if context.job_queue is not None:
            context.job_queue.run_once(ensure_queue_job, 300)
