from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from panimau_bot.config import Settings
from panimau_bot.services.downloader import SocialVideoDownloader


class ConfigTests(unittest.TestCase):
    def test_parses_admin_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "token",
                "GROUP_ID": "-100123",
                "CHANNEL_ID": "@channel",
                "ADMIN_IDS": "1, 2,3",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.admin_ids, (1, 2, 3))

    def test_uses_default_delay_and_no_cookiefile(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "token",
                "GROUP_ID": "-100123",
                "CHANNEL_ID": "@channel",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            downloader = SocialVideoDownloader(cookiefile=settings.ytdlp_cookies_file)

        self.assertEqual(settings.download_delay_seconds, 5)
        self.assertIsNone(settings.ytdlp_cookies_file)
        self.assertNotIn("cookiefile", downloader._build_options("/tmp/test.%(ext)s"))

    def test_passes_cookiefile_when_configured(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "token",
                "GROUP_ID": "-100123",
                "CHANNEL_ID": "@channel",
                "YTDLP_COOKIES_FILE": "/tmp/cookies.txt",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            downloader = SocialVideoDownloader(cookiefile=settings.ytdlp_cookies_file)

        self.assertEqual(settings.ytdlp_cookies_file, "/tmp/cookies.txt")
        self.assertEqual(
            downloader._build_options("/tmp/test.%(ext)s")["cookiefile"],
            "/tmp/cookies.txt",
        )


if __name__ == "__main__":
    unittest.main()
