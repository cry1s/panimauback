from __future__ import annotations

import os
from dataclasses import dataclass


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
    ytdlp_cookies_file: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=_required_env("BOT_TOKEN"),
            group_id=int(_required_env("GROUP_ID")),
            channel_id=_required_env("CHANNEL_ID"),
            admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            download_delay_seconds=int(os.getenv("DOWNLOAD_DELAY_SECONDS", "5")),
            ytdlp_cookies_file=os.getenv("YTDLP_COOKIES_FILE") or None,
        )
