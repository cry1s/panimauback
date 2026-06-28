from __future__ import annotations

import os
from pathlib import Path
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

    def test_uses_default_delay_and_state_dir(self) -> None:
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
            downloader = SocialVideoDownloader(cookiefile=settings.instagram_cookies_file)

        self.assertEqual(settings.download_delay_seconds, 5)
        self.assertEqual(settings.state_dir, Path("data"))
        self.assertEqual(settings.instagram_cookies_file, Path("data") / "instagram.cookies.txt")
        self.assertEqual(
            downloader._build_options("/tmp/test.%(ext)s")["cookiefile"],
            str(Path("data") / "instagram.cookies.txt"),
        )

    def test_parses_state_dir_when_configured(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "token",
                "GROUP_ID": "-100123",
                "CHANNEL_ID": "@channel",
                "BOT_STATE_DIR": "/tmp/panimau-state",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.state_dir, Path("/tmp/panimau-state"))
        self.assertEqual(settings.instagram_cookies_file, Path("/tmp/panimau-state") / "instagram.cookies.txt")

    def test_prefers_single_file_format_without_ffmpeg(self) -> None:
        downloader = SocialVideoDownloader(ffmpeg_available=False)

        options = downloader._build_options("/tmp/test.%(ext)s")

        self.assertNotIn("+", options["format"])
        self.assertNotIn("merge_output_format", options)

    def test_enables_merge_when_ffmpeg_available(self) -> None:
        downloader = SocialVideoDownloader(ffmpeg_available=True)

        options = downloader._build_options("/tmp/test.%(ext)s")

        self.assertIn("+", options["format"])
        self.assertEqual(options["merge_output_format"], "mp4")

    def test_normal_download_options_do_not_include_credentials(self) -> None:
        downloader = SocialVideoDownloader(cookiefile="/tmp/cookies.txt")

        options = downloader._build_options("/tmp/test.%(ext)s")

        self.assertEqual(options["cookiefile"], "/tmp/cookies.txt")
        self.assertNotIn("username", options)
        self.assertNotIn("password", options)
        self.assertNotIn("twofactor", options)


if __name__ == "__main__":
    unittest.main()
