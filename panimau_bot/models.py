from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from telegram import Message

if TYPE_CHECKING:
    from panimau_bot.config import Settings
    from panimau_bot.services.downloader import SocialVideoDownloader
    from panimau_bot.stats import BotStats

AttachmentItem = tuple[str, str]


@dataclass(slots=True)
class DownloadRequest:
    url: str
    platform: str


@dataclass(slots=True)
class DownloadResult:
    file_path: Path
    url: str
    platform: str


@dataclass(slots=True)
class PendingAttachmentPost:
    source_msg: Message
    cancel_msg: Message
    file_types: list[AttachmentItem]


@dataclass(slots=True)
class PendingDownloadPost:
    source_msg: Message
    cancel_msg: Message
    request: DownloadRequest


PendingPost = PendingAttachmentPost | PendingDownloadPost


class PendingStore:
    def __init__(self) -> None:
        self._posts: dict[str, PendingPost] = {}

    def get(self, post_id: str) -> PendingPost | None:
        return self._posts.get(post_id)

    def set(self, post_id: str, post: PendingPost) -> None:
        self._posts[post_id] = post

    def pop(self, post_id: str, default: PendingPost | None = None) -> PendingPost | None:
        return self._posts.pop(post_id, default)


@dataclass(slots=True)
class AppServices:
    settings: "Settings"
    stats: "BotStats"
    pending_store: PendingStore
    downloader: "SocialVideoDownloader"
