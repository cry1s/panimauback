from __future__ import annotations

import unittest

from panimau_bot.services.downloader import detect_platform, extract_download_request


class SocialUrlTests(unittest.TestCase):
    def test_extracts_first_supported_url(self) -> None:
        text = (
            "сначала вот это https://www.instagram.com/reel/Cop84x6u7CP/, "
            "а потом https://www.tiktok.com/@scout2015/video/6718335390845095173"
        )

        request = extract_download_request(text)

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.platform, "instagram")
        self.assertEqual(request.url, "https://www.instagram.com/reel/Cop84x6u7CP/")

    def test_detects_supported_platforms(self) -> None:
        cases = {
            "youtube.com/shorts/abc123": "youtube",
            "https://youtu.be/dQw4w9WgXcQ": "youtube",
            "https://www.instagram.com/user/reel/CWqAgUZgCku/": "instagram",
            "https://vm.tiktok.com/ZTR45GpSF/": "tiktok",
            "https://vt.tiktok.com/ZSe4FqkKd": "tiktok",
            "https://www.tiktok.com/@leenabhushan/video/6748451240264420610": "tiktok",
        }

        for url, expected_platform in cases.items():
            with self.subTest(url=url):
                self.assertEqual(detect_platform(url), expected_platform)

    def test_ignores_unsupported_urls(self) -> None:
        self.assertIsNone(extract_download_request("смотри https://www.instagram.com/p/Cop84x6u7CP/"))
        self.assertIsNone(extract_download_request("смотри https://example.com/video/123"))

    def test_strips_trailing_punctuation(self) -> None:
        request = extract_download_request("глянь https://www.instagram.com/reel/Cop84x6u7CP/).")

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.url, "https://www.instagram.com/reel/Cop84x6u7CP/")


if __name__ == "__main__":
    unittest.main()
