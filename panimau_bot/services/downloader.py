from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import yt_dlp

from panimau_bot.models import DownloadRequest, DownloadResult

TRAILING_URL_PUNCTUATION = ".,!?;:)]}"
INSTAGRAM_AUTH_ERROR_MARKERS = (
    "empty media response",
    "login",
    "logged-in",
    "log in",
    "cookies",
    "authentication",
    "private",
)

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


@dataclass(slots=True, frozen=True)
class DownloaderCredentials:
    username: str
    password: str
    twofactor: str | None = None


class InstagramAuthRequiredError(RuntimeError):
    """Raised when Instagram refuses unauthenticated or stale-cookie requests."""


class SocialVideoDownloader:
    def __init__(self, cookiefile: str | Path | None = None, ffmpeg_available: bool | None = None) -> None:
        self.cookiefile = str(cookiefile) if cookiefile is not None else None
        self.ffmpeg_available = (
            ffmpeg_available
            if ffmpeg_available is not None
            else shutil.which("ffmpeg") is not None
        )

    def _build_options(
        self,
        output_template: str | None = None,
        credentials: DownloaderCredentials | None = None,
    ) -> dict[str, object]:
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
            "quiet": True,
            "noplaylist": True,
        }

        if output_template is not None:
            options["outtmpl"] = output_template

        if self.ffmpeg_available:
            options["merge_output_format"] = "mp4"

        if self.cookiefile:
            options["cookiefile"] = self.cookiefile

        if credentials is not None:
            options["username"] = credentials.username
            options["password"] = credentials.password
            if credentials.twofactor:
                options["twofactor"] = credentials.twofactor

        return options

    def _raise_for_auth_error(self, request: DownloadRequest, exc: Exception) -> None:
        if request.platform != "instagram":
            raise exc

        error_text = str(exc).lower()
        if any(marker in error_text for marker in INSTAGRAM_AUTH_ERROR_MARKERS):
            raise InstagramAuthRequiredError("Instagram needs /ig_login") from exc

        raise exc

    def probe(
        self,
        request: DownloadRequest,
        credentials: DownloaderCredentials | None = None,
    ) -> dict[str, object]:
        try:
            with yt_dlp.YoutubeDL(self._build_options(credentials=credentials)) as downloader:
                info = downloader.extract_info(request.url, download=False)
        except Exception as exc:
            self._raise_for_auth_error(request, exc)

        if not isinstance(info, dict):
            return {}

        return info

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

        try:
            with yt_dlp.YoutubeDL(self._build_options(output_template)) as downloader:
                info = downloader.extract_info(request.url, download=True)
                prepared_path = Path(downloader.prepare_filename(info))
        except Exception as exc:
            self._raise_for_auth_error(request, exc)

        return DownloadResult(
            file_path=self._resolve_downloaded_file(output_prefix, prepared_path).resolve(),
            url=request.url,
            platform=request.platform,
        )
