from __future__ import annotations

import unittest
from unittest.mock import patch

from panimau_bot.models import DownloadRequest
from panimau_bot.services.downloader import (
    DownloaderCredentials,
    InstagramAuthRequiredError,
    SocialVideoDownloader,
)


class DownloaderTests(unittest.TestCase):
    def test_probe_passes_credentials_only_when_requested(self) -> None:
        request = DownloadRequest(
            url="https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ==",
            platform="instagram",
        )

        with patch("panimau_bot.services.downloader.yt_dlp.YoutubeDL") as youtube_dl:
            instance = youtube_dl.return_value.__enter__.return_value
            instance.extract_info.return_value = {"title": "ok"}
            downloader = SocialVideoDownloader(cookiefile="/tmp/cookies.txt", ffmpeg_available=True)

            info = downloader.probe(request, DownloaderCredentials("user", "secret", "123456"))

        self.assertEqual(info, {"title": "ok"})
        options = youtube_dl.call_args.args[0]
        self.assertEqual(options["cookiefile"], "/tmp/cookies.txt")
        self.assertEqual(options["username"], "user")
        self.assertEqual(options["password"], "secret")
        self.assertEqual(options["twofactor"], "123456")

    def test_instagram_auth_errors_are_translated(self) -> None:
        request = DownloadRequest(
            url="https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ==",
            platform="instagram",
        )

        with patch("panimau_bot.services.downloader.yt_dlp.YoutubeDL") as youtube_dl:
            instance = youtube_dl.return_value.__enter__.return_value
            instance.extract_info.side_effect = RuntimeError("Instagram sent an empty media response; use cookies")
            downloader = SocialVideoDownloader(cookiefile="/tmp/cookies.txt")

            with self.assertRaises(InstagramAuthRequiredError):
                downloader.probe(request)


if __name__ == "__main__":
    unittest.main()
