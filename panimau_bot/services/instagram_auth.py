from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from panimau_bot.models import DownloadRequest, DownloadResult
from panimau_bot.services.downloader import (
    DownloaderCredentials,
    InstagramAuthRequiredError,
    SocialVideoDownloader,
    extract_download_request,
)

DEFAULT_INSTAGRAM_TEST_URL = "https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ=="


@dataclass(slots=True, frozen=True)
class InstagramAuthStatus:
    has_cookiefile: bool
    cookies_updated_at: datetime | None
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_message: str | None


class InstagramAuthService:
    def __init__(self, cookiefile: Path, downloader: SocialVideoDownloader) -> None:
        self.cookiefile = cookiefile
        self.downloader = downloader
        self._last_test_at: datetime | None = None
        self._last_test_ok: bool | None = None
        self._last_test_message: str | None = None

    def status(self) -> InstagramAuthStatus:
        updated_at = None
        if self.cookiefile.exists():
            updated_at = datetime.fromtimestamp(self.cookiefile.stat().st_mtime).replace(microsecond=0)

        return InstagramAuthStatus(
            has_cookiefile=self.cookiefile.exists(),
            cookies_updated_at=updated_at,
            last_test_at=self._last_test_at,
            last_test_ok=self._last_test_ok,
            last_test_message=self._last_test_message,
        )

    def save_cookie_text(self, raw_text: str) -> None:
        cleaned_text = raw_text.strip()
        self._validate_cookie_text(cleaned_text)

        self.cookiefile.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.cookiefile.with_name(f"{self.cookiefile.name}.tmp")
        temporary_path.write_text(f"{cleaned_text}\n", encoding="utf-8")
        temporary_path.replace(self.cookiefile)

    def save_cookie_bytes(self, raw_bytes: bytes) -> None:
        try:
            raw_text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("cookies.txt must be UTF-8 text") from exc

        self.save_cookie_text(raw_text)

    def logout(self) -> bool:
        if not self.cookiefile.exists():
            return False

        self.cookiefile.unlink()
        return True

    def verify_credentials(
        self,
        username: str,
        password: str,
        twofactor: str | None = None,
        test_url: str = DEFAULT_INSTAGRAM_TEST_URL,
    ) -> str:
        request = self._build_instagram_request(test_url)
        self.cookiefile.parent.mkdir(parents=True, exist_ok=True)
        credentials = DownloaderCredentials(
            username=username.strip(),
            password=password,
            twofactor=twofactor.strip() if twofactor and twofactor.strip() else None,
        )

        try:
            info = self.downloader.probe(request, credentials=credentials)
        except Exception as exc:
            self._remember_test(False, exc)
            raise

        message = self._describe_probe_result(info)
        self._remember_test(True, message)
        return message

    def test_url(self, raw_url: str = DEFAULT_INSTAGRAM_TEST_URL) -> str:
        request = self._build_instagram_request(raw_url)
        result: DownloadResult | None = None

        try:
            result = self.downloader.download(request)
            size = result.file_path.stat().st_size if result.file_path.exists() else 0
        except Exception as exc:
            self._remember_test(False, exc)
            raise
        finally:
            if result is not None and result.file_path.exists():
                result.file_path.unlink(missing_ok=True)

        message = f"download ok, {size} bytes"
        self._remember_test(True, message)
        return message

    def _remember_test(self, ok: bool, message: object) -> None:
        self._last_test_at = datetime.now().replace(microsecond=0)
        self._last_test_ok = ok
        self._last_test_message = str(message)

    def _build_instagram_request(self, raw_url: str) -> DownloadRequest:
        request = extract_download_request(raw_url.strip())
        if request is None or request.platform != "instagram":
            raise ValueError("Send an Instagram Reels URL")

        return request

    def _describe_probe_result(self, info: dict[str, object]) -> str:
        title = info.get("title") or info.get("id") or "Instagram reel"
        return f"login ok: {title}"

    def _validate_cookie_text(self, raw_text: str) -> None:
        if not raw_text:
            raise ValueError("cookies.txt is empty")

        first_non_empty = next((line.strip() for line in raw_text.splitlines() if line.strip()), "")
        if first_non_empty.startswith(("{", "[")):
            raise ValueError("cookies.txt must use Netscape format, not JSON")

        has_cookie_row = False
        has_instagram_cookie = False
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            fields = stripped.split("\t")
            if len(fields) != 7:
                raise ValueError("cookies.txt must use Netscape format with 7 tab-separated fields")

            has_cookie_row = True
            if "instagram.com" in fields[0].lower():
                has_instagram_cookie = True

        if not has_cookie_row:
            raise ValueError("cookies.txt has no cookie rows")
        if not has_instagram_cookie:
            raise ValueError("cookies.txt has no Instagram cookies")


def is_instagram_auth_error(error: Exception) -> bool:
    return isinstance(error, InstagramAuthRequiredError)
