from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from telegram.constants import ChatType

from panimau_bot.handlers.instagram_auth import _is_admin_private
from panimau_bot.models import DownloadRequest, DownloadResult
from panimau_bot.services.downloader import DownloaderCredentials
from panimau_bot.services.instagram_auth import InstagramAuthService

VALID_COOKIES = """# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	2147483647	sessionid	abc123
"""


class FakeDownloader:
    def __init__(self, download_path: Path | None = None) -> None:
        self.download_path = download_path
        self.probe_calls: list[tuple[DownloadRequest, DownloaderCredentials | None]] = []
        self.download_calls: list[DownloadRequest] = []

    def probe(
        self,
        request: DownloadRequest,
        credentials: DownloaderCredentials | None = None,
    ) -> dict[str, object]:
        self.probe_calls.append((request, credentials))
        return {"title": "canary reel"}

    def download(self, request: DownloadRequest) -> DownloadResult:
        self.download_calls.append(request)
        assert self.download_path is not None
        self.download_path.write_bytes(b"video")
        return DownloadResult(
            file_path=self.download_path,
            url=request.url,
            platform=request.platform,
        )


class InstagramAuthServiceTests(unittest.TestCase):
    def test_saves_valid_cookie_text_and_reports_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cookiefile = Path(tmp) / "instagram.cookies.txt"
            service = InstagramAuthService(cookiefile, FakeDownloader())

            service.save_cookie_text(VALID_COOKIES)
            status = service.status()

            self.assertTrue(cookiefile.exists())
            self.assertTrue(status.has_cookiefile)
            self.assertIsNotNone(status.cookies_updated_at)

    def test_rejects_invalid_cookie_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = InstagramAuthService(Path(tmp) / "instagram.cookies.txt", FakeDownloader())

            with self.assertRaisesRegex(ValueError, "Netscape"):
                service.save_cookie_text('{"cookies": []}')

            with self.assertRaisesRegex(ValueError, "Instagram"):
                service.save_cookie_text(".example.com\tTRUE\t/\tTRUE\t2147483647\tsessionid\tabc123")

    def test_verify_credentials_uses_one_shot_downloader_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_downloader = FakeDownloader()
            service = InstagramAuthService(Path(tmp) / "instagram.cookies.txt", fake_downloader)

            result = service.verify_credentials("user", "secret", "123456")

            self.assertIn("login ok", result)
            self.assertEqual(len(fake_downloader.probe_calls), 1)
            _, credentials = fake_downloader.probe_calls[0]
            self.assertIsNotNone(credentials)
            assert credentials is not None
            self.assertEqual(credentials.username, "user")
            self.assertEqual(credentials.password, "secret")
            self.assertEqual(credentials.twofactor, "123456")

    def test_test_url_downloads_and_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            download_path = Path(tmp) / "probe.mp4"
            fake_downloader = FakeDownloader(download_path)
            service = InstagramAuthService(Path(tmp) / "instagram.cookies.txt", fake_downloader)

            result = service.test_url("https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ==")

            self.assertIn("download ok", result)
            self.assertFalse(download_path.exists())
            self.assertEqual(len(fake_downloader.download_calls), 1)

    def test_logout_removes_cookiefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cookiefile = Path(tmp) / "instagram.cookies.txt"
            service = InstagramAuthService(cookiefile, FakeDownloader())
            service.save_cookie_text(VALID_COOKIES)

            self.assertTrue(service.logout())
            self.assertFalse(cookiefile.exists())
            self.assertFalse(service.logout())

    def test_admin_private_gating(self) -> None:
        services = SimpleNamespace(settings=SimpleNamespace(admin_ids=(10,)))

        private_admin_update = SimpleNamespace(
            effective_user=SimpleNamespace(id=10),
            effective_chat=SimpleNamespace(type=ChatType.PRIVATE),
        )
        group_admin_update = SimpleNamespace(
            effective_user=SimpleNamespace(id=10),
            effective_chat=SimpleNamespace(type=ChatType.GROUP),
        )
        private_non_admin_update = SimpleNamespace(
            effective_user=SimpleNamespace(id=11),
            effective_chat=SimpleNamespace(type=ChatType.PRIVATE),
        )

        self.assertTrue(_is_admin_private(private_admin_update, services))
        self.assertFalse(_is_admin_private(group_admin_update, services))
        self.assertFalse(_is_admin_private(private_non_admin_update, services))


if __name__ == "__main__":
    unittest.main()
