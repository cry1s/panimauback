from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import requests
import yt_dlp
from yt_dlp.utils import DownloadError

from panimau_bot.models import DownloadRequest, DownloadResult

logger = logging.getLogger(__name__)

TRAILING_URL_PUNCTUATION = ".,!?;:)]}"

INSTAGRAM_EMBED_URL = "https://www.instagram.com/p/{shortcode}/embed/captioned/"
INSTAGRAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
}

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
            r"(?:(?:https?://)?(?:www\.)?instagram\.com/(?:[^/\s?#]+/)?(?:p|reels?)/(?!audio/)[^\s]+)",
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


def extract_instagram_shortcode(url: str) -> str | None:
    match = re.search(r"instagram\.com/(?:[^/?#\s]+/)?p/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


def _dedupe_media_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        key = urlparse(url).path
        if key not in seen:
            seen.add(key)
            unique.append(url)
    return unique


def _urls_from_embed_context(html_text: str) -> list[str]:
    """Полный альбом прячется в contextJSON -> gql_data -> shortcode_media."""
    marker = html_text.find('"contextJSON"')
    if marker == -1:
        return []

    try:
        colon = html_text.index(":", marker)
        quote = html_text.index('"', colon)
        value, _ = json.JSONDecoder().raw_decode(html_text[quote:])
        if isinstance(value, str):
            data = json.loads(value)
        elif isinstance(value, dict):
            inner = value.get("contextJSON", value)
            data = json.loads(inner) if isinstance(inner, str) else inner
        else:
            data = {}
        media = (data.get("gql_data") or {}).get("shortcode_media") or {}
    except (ValueError, AttributeError, TypeError, json.JSONDecodeError):
        return []

    nodes: list[dict] = []
    sidecar = media.get("edge_sidecar_to_children")
    if isinstance(sidecar, dict):
        nodes = [edge.get("node") or {} for edge in sidecar.get("edges") or []]
    elif media:
        nodes = [media]

    urls: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("__typename") == "GraphVideo" or node.get("is_video"):
            continue
        url = node.get("display_url") or node.get("display_src")
        if isinstance(url, str) and url.startswith("http"):
            urls.append(url)
    return urls


def _urls_from_embed_images(html_text: str) -> list[str]:
    urls: list[str] = []
    for tag in re.findall(r"<img\b[^>]*>", html_text):
        if "EmbeddedMediaImage" not in tag:
            continue
        src = re.search(r'src="([^"]+)"', tag)
        if src and src.group(1).startswith("http"):
            urls.append(src.group(1))
    return urls


def parse_instagram_embed(html_text: str) -> list[str]:
    return _dedupe_media_urls(_urls_from_embed_context(html_text)) or _dedupe_media_urls(
        _urls_from_embed_images(html_text)
    )


def extract_image_urls_from_info(info: object) -> list[str]:
    """Фото-посты не дают форматов, но несут полноразмерные картинки в thumbnails."""
    if not isinstance(info, dict):
        return []

    if info.get("_type") == "playlist":
        sources = [entry for entry in info.get("entries") or [] if isinstance(entry, dict)]
    else:
        sources = [info]

    urls: list[str] = []
    for source in sources:
        thumbnails = [
            thumb
            for thumb in source.get("thumbnails") or []
            if isinstance(thumb, dict) and isinstance(thumb.get("url"), str)
        ]
        if thumbnails:
            best = max(
                thumbnails,
                key=lambda thumb: (
                    thumb.get("preference") or 0,
                    thumb.get("width") or 0,
                ),
            )
            urls.append(best["url"])
    return urls


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
    def __init__(self, ffmpeg_available: bool | None = None) -> None:
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
        }

        if self.ffmpeg_available:
            options["merge_output_format"] = "mp4"

        return options

    def download(self, request: DownloadRequest) -> DownloadResult:
        output_dir = Path(tempfile.gettempdir()) / f"panimau_{request.platform}_{uuid4().hex}"
        output_template = str(output_dir / "%(id)s.%(ext)s")

        options = self._build_options(output_template)
        if request.platform == "instagram":
            options["ignore_no_formats"] = True

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(request.url, download=True)

            if info is None:
                raise RuntimeError(f"Извлечение не дало результата: {request.url}")

            file_paths = (
                tuple(
                    path.resolve()
                    for path in sorted(output_dir.iterdir())
                    if path.is_file()
                )
                if output_dir.exists()
                else ()
            )

            if not file_paths:
                image_urls = extract_image_urls_from_info(info)
                if image_urls:
                    saved = self._save_url_list(output_dir, image_urls)
                    return DownloadResult(
                        file_paths=tuple(path.resolve() for path in saved),
                        url=request.url,
                        platform=request.platform,
                    )
                raise FileNotFoundError(f"Downloaded files were not found for {output_dir.name}")
        except DownloadError as exc:
            shutil.rmtree(output_dir, ignore_errors=True)
            if request.platform == "instagram":
                try:
                    photo_files = self._download_instagram_photos(request.url)
                except Exception:
                    logger.warning(
                        "Фолбэк через embed не сработал для %s", request.url, exc_info=True
                    )
                else:
                    if photo_files:
                        return DownloadResult(
                            file_paths=photo_files,
                            url=request.url,
                            platform=request.platform,
                        )
            raise
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

        return DownloadResult(
            file_paths=file_paths,
            url=request.url,
            platform=request.platform,
        )

    def _save_url_list(self, output_dir: Path, urls: list[str], prefix: str = "photo") -> tuple[Path, ...]:
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            file_paths: list[Path] = []
            for index, media_url in enumerate(urls):
                target = output_dir / f"{prefix}_{index:02d}.jpg"
                response = requests.get(media_url, headers=INSTAGRAM_HEADERS, timeout=30)
                response.raise_for_status()
                target.write_bytes(response.content)
                file_paths.append(target)
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

        return tuple(file_paths)

    def _download_instagram_photos(self, url: str) -> tuple[Path, ...]:
        shortcode = extract_instagram_shortcode(url)
        if not shortcode:
            return ()

        embed_response = requests.get(
            INSTAGRAM_EMBED_URL.format(shortcode=shortcode),
            headers=INSTAGRAM_HEADERS,
            timeout=30,
        )
        embed_response.raise_for_status()

        media_urls = parse_instagram_embed(embed_response.text)
        if not media_urls:
            logger.warning(
                "Embed для %s отдал страницу без медиа (status=%s, %s байт)",
                shortcode,
                embed_response.status_code,
                len(embed_response.text),
            )
            return ()

        output_dir = Path(tempfile.gettempdir()) / f"panimau_instaphoto_{uuid4().hex}"
        return self._save_url_list(output_dir, media_urls)
