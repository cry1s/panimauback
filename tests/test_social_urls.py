from __future__ import annotations

import json
import unittest

from panimau_bot.services.downloader import (
    detect_platform,
    extract_download_request,
    extract_image_urls_from_info,
    extract_instagram_shortcode,
    parse_instagram_embed,
)


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
            "https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ==": "instagram",
            "https://www.instagram.com/p/DcMS0FhsqGQ/?igsi=MTBzZDd6dnR4bnVnbw==": "instagram",
            "https://www.instagram.com/p/Cop84x6u7CP/": "instagram",
            "https://www.instagram.com/user/p/Cop84x6u7CP/": "instagram",
            "https://vm.tiktok.com/ZTR45GpSF/": "tiktok",
            "https://vt.tiktok.com/ZSe4FqkKd": "tiktok",
            "https://www.tiktok.com/@leenabhushan/video/6748451240264420610": "tiktok",
        }

        for url, expected_platform in cases.items():
            with self.subTest(url=url):
                self.assertEqual(detect_platform(url), expected_platform)

    def test_ignores_unsupported_urls(self) -> None:
        self.assertIsNone(extract_download_request("смотри https://example.com/video/123"))
        self.assertIsNone(
            extract_download_request("аудио https://www.instagram.com/reel/audio/12345/")
        )

    def test_strips_trailing_punctuation(self) -> None:
        request = extract_download_request("глянь https://www.instagram.com/reel/Cop84x6u7CP/).")

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.url, "https://www.instagram.com/reel/Cop84x6u7CP/")

    def test_extracts_canary_reel_with_query_string(self) -> None:
        request = extract_download_request(
            "проверь https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ=="
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.platform, "instagram")
        self.assertEqual(
            request.url,
            "https://www.instagram.com/reel/DZ-ec0ixTgg/?igsh=MXNvaWdoYXU1dzduNQ==",
        )

    def test_extracts_canary_post_with_query_string(self) -> None:
        request = extract_download_request(
            "проверь https://www.instagram.com/p/DcMS0FhsqGQ/?igsi=MTBzZDd6dnR4bnVnbw=="
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.platform, "instagram")
        self.assertEqual(
            request.url,
            "https://www.instagram.com/p/DcMS0FhsqGQ/?igsi=MTBzZDd6dnR4bnVnbw==",
        )


class InstagramEmbedTests(unittest.TestCase):
    def test_extracts_shortcode_from_post_urls(self) -> None:
        cases = {
            "https://www.instagram.com/p/DcMS0FhsqGQ/?igsi=MTBzZDd6dnR4bnVnbw==": "DcMS0FhsqGQ",
            "https://www.instagram.com/user/p/Cop84x6u7CP/": "Cop84x6u7CP",
            "https://instagram.com/p/aye83DjauH/embed/": "aye83DjauH",
            "https://www.instagram.com/reel/DZ-ec0ixTgg/": None,
        }

        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(extract_instagram_shortcode(url), expected)

    @staticmethod
    def build_embed_html() -> str:
        inner = {
            "gql_data": {
                "shortcode_media": {
                    "__typename": "GraphSidecar",
                    "edge_sidecar_to_children": {
                        "edges": [
                            {"node": {"__typename": "GraphImage", "display_url": "https://cdn/one.jpg?stp=a"}},
                            {
                                "node": {
                                    "__typename": "GraphVideo",
                                    "display_url": "https://cdn/thumb.jpg",
                                    "video_url": "https://cdn/v.mp4",
                                }
                            },
                            {"node": {"__typename": "GraphImage", "display_url": "https://cdn/two.jpg"}},
                        ]
                    },
                }
            }
        }

        return (
            '<div><img class="EmbeddedMediaImage" src="https://cdn/one.jpg?stp=b" /></div>'
            '<script>window.a={"contextJSON":' + json.dumps(json.dumps(inner)) + "};</script>"
        )

    def test_parse_embed_context_json_skips_videos_and_dedupes(self) -> None:
        urls = parse_instagram_embed(self.build_embed_html())

        self.assertEqual(["https://cdn/one.jpg?stp=a", "https://cdn/two.jpg"], urls)

    def test_parse_embed_falls_back_to_image_tag(self) -> None:
        html = (
            '<img class="EmbeddedMediaImage" src="https://cdn/single.jpg?x=1" />'
            "<script>var noContextHere = true;</script>"
        )

        self.assertEqual(["https://cdn/single.jpg?x=1"], parse_instagram_embed(html))

    def test_parse_embed_dedupes_by_path(self) -> None:
        html = '<img class="EmbeddedMediaImage" src="https://cdn/a.jpg?p=1"><img class="EmbeddedMediaImage" src="https://other.cdn/a.jpg?p=2">'

        self.assertEqual(1, len(parse_instagram_embed(html)))

    def test_parse_embed_returns_empty_for_garbage(self) -> None:
        self.assertEqual([], parse_instagram_embed("<html>login page</html>"))


class ImageUrlsFromInfoTests(unittest.TestCase):
    def test_single_photo_post_picks_largest_thumbnail(self) -> None:
        info = {
            "thumbnails": [
                {"url": "small", "width": 150, "height": 150, "preference": -10},
                {"url": "large", "width": 1080, "height": 1350, "preference": -10},
            ]
        }

        self.assertEqual(["large"], extract_image_urls_from_info(info))

    def test_carousel_playlist_returns_one_url_per_entry(self) -> None:
        info = {
            "_type": "playlist",
            "entries": [
                {"thumbnails": [{"url": "first", "width": 640}]},
                {"thumbnails": [{"url": "second", "width": 640}]},
                None,
                {"formats": [], "thumbnails": []},
            ],
        }

        self.assertEqual(["first", "second"], extract_image_urls_from_info(info))

    def test_video_post_without_thumbnails_yields_nothing(self) -> None:
        self.assertEqual([], extract_image_urls_from_info({"formats": [{"url": "v.mp4"}]}))
        self.assertEqual([], extract_image_urls_from_info(None))


if __name__ == "__main__":
    unittest.main()
