from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import yt_dlp

from panimau_bot.models import DownloadRequest, DownloadResult

TRAILING_URL_PUNCTUATION = ".,!?;:)]}"

SUPPORTED_URL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "youtube",
        re.compile(
            r"(?:(?:https?://)?(?:www\.)?(?:youtube\.com/shorts/[^\s]+|youtu\.be/[^\s]+))",
            re.IGNORECASE,
        ),
    ),
    (
        "instagram",
        re.compile(
            r"(?:(?:https?://)?(?:www\.)?instagram\.com/(?:[^/\s?#]+/)?reels?/(?!audio/)[^\s]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "tiktok",
        re.compile(
            r"(?:(?:https?://)?(?:www\.)?(?:tiktok\.com/@[^/\s?#]+/video/[^\s]+|vm\.tiktok\.com/[^\s]+|vt\.tiktok\.com/[^\s]+))",
            re.IGNORECASE,
        ),
    ),
)


def _normalize_url(raw_url: str) -> str:
    cleaned = raw_url.rstrip(TRAILING_URL_PUNCTUATION)
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"


def detect_platform(url: str) -> str | None:
    normalized_url = _normalize_url(url)
    for platform, pattern in SUPPORTED_URL_PATTERNS:
        if pattern.fullmatch(normalized_url):
            return platform
    return None


def extract_download_request(text: str) -> DownloadRequest | None:
    earliest_match: tuple[int, DownloadRequest] | None = None

    for platform, pattern in SUPPORTED_URL_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue

        request = DownloadRequest(
            url=_normalize_url(match.group(0)),
            platform=platform,
        )

        if earliest_match is None or match.start() < earliest_match[0]:
            earliest_match = (match.start(), request)

    if earliest_match is None:
        return None

    return earliest_match[1]


class SocialVideoDownloader:
    def __init__(self, cookiefile: str | None = None, ffmpeg_available: bool | None = None) -> None:
        self.cookiefile = cookiefile
        self.ffmpeg_available = (
            ffmpeg_available
            if ffmpeg_available is not None
            else shutil.which("ffmpeg") is not None
        )

    def _build_options(self, output_template: str) -> dict[str, object]:
        format_selector = (
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[height<=720]/b"
            if self.ffmpeg_available
            else (
                "b[height<=720][vcodec!=none][acodec!=none][ext=mp4]/"
                "b[vcodec!=none][acodec!=none][ext=mp4]/"
                "b[height<=720][vcodec!=none][acodec!=none]/"
                "b[vcodec!=none][acodec!=none]"
            )
        )
        options: dict[str, object] = {
            "format": format_selector,
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
        }

        if self.ffmpeg_available:
            options["merge_output_format"] = "mp4"

        if self.cookiefile:
            options["cookiefile"] = self.cookiefile

        return options

    def _resolve_downloaded_file(self, output_prefix: Path, prepared_path: Path) -> Path:
        candidates = [
            prepared_path,
            prepared_path.with_suffix(".mp4"),
            output_prefix.with_suffix(".mp4"),
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        wildcard_candidates = sorted(output_prefix.parent.glob(f"{output_prefix.name}.*"))
        for candidate in wildcard_candidates:
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(f"Downloaded file was not found for {output_prefix.name}")

    def download(self, request: DownloadRequest) -> DownloadResult:
        output_prefix = Path(tempfile.gettempdir()) / f"panimau_{request.platform}_{uuid4().hex}"
        output_template = f"{output_prefix}.%(ext)s"

        with yt_dlp.YoutubeDL(self._build_options(output_template)) as downloader:
            info = downloader.extract_info(request.url, download=True)
            prepared_path = Path(downloader.prepare_filename(info))

        return DownloadResult(
            file_path=self._resolve_downloaded_file(output_prefix, prepared_path).resolve(),
            url=request.url,
            platform=request.platform,
        )
