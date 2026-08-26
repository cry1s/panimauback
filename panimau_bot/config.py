from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable {name} is required")
    return value


def _parse_admin_ids(raw_value: str) -> tuple[int, ...]:
    if not raw_value.strip():
        return ()
    return tuple(int(item.strip()) for item in raw_value.split(",") if item.strip())


@dataclass(slots=True, frozen=True)
class Settings:
    bot_token: str
    group_id: int
    channel_id: str
    admin_ids: tuple[int, ...]
    download_delay_seconds: int = 5
    state_dir: Path = Path("data")
    vk_service_token: str = ""
    vk_source_domain: str = "panim4u"
    archive_trigger_posts: int = 3
    archive_min_delay_seconds: int = 3600
    archive_max_delay_seconds: int = 86400

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=_required_env("BOT_TOKEN"),
            group_id=int(_required_env("GROUP_ID")),
            channel_id=_required_env("CHANNEL_ID"),
            admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            download_delay_seconds=int(os.getenv("DOWNLOAD_DELAY_SECONDS", "5")),
            state_dir=Path(os.getenv("BOT_STATE_DIR", "data")),
            vk_service_token=os.getenv("VK_SERVICE_TOKEN", ""),
            vk_source_domain=os.getenv("VK_SOURCE_DOMAIN", "panim4u"),
            archive_trigger_posts=int(os.getenv("ARCHIVE_TRIGGER_POSTS", "3")),
            archive_min_delay_seconds=int(os.getenv("ARCHIVE_MIN_DELAY_SECONDS", "3600")),
            archive_max_delay_seconds=int(os.getenv("ARCHIVE_MAX_DELAY_SECONDS", "86400")),
        )
