from __future__ import annotations

import re
import unittest
from datetime import datetime

from panimau_bot import voice
from panimau_bot.services.instagram_auth import InstagramAuthStatus
from panimau_bot.stats import BotStats


class VoiceTests(unittest.TestCase):
    def test_render_health_includes_values_and_no_placeholders(self) -> None:
        text = voice.render_health(
            uptime="1д 2ч 3м",
            total_forwarded=7,
            cancelled=2,
            joke="тестовый панч",
        )

        self.assertIn("1д 2ч 3м", text)
        self.assertIn("7", text)
        self.assertIn("2", text)
        self.assertIn("тестовый панч", text)
        self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_stats_includes_counts_and_type_breakdown(self) -> None:
        stats = BotStats()
        stats.add_forward("youtube")
        stats.add_forward("photo")
        stats.add_cancel()

        text = voice.render_stats(stats)

        self.assertIn("Всего попыток: 3", text)
        self.assertIn("Долетело в канал: 2", text)
        self.assertIn("Отменено по дороге: 1", text)
        self.assertIn("youtube: 1", text)
        self.assertIn("photo: 1", text)
        self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_social_templates_include_label_url_error_and_delay(self) -> None:
        queue_text = voice.render_social_queue("рилс", 5)
        progress_text = voice.render_social_progress("рилс")
        success_text = voice.render_social_success("рилс")
        caption_text = voice.render_social_reply_caption(
            label="рилс",
            url="https://example.com/reel",
            link="https://t.me/channel/1",
        )
        error_text = voice.render_social_error("рилс", "boom")
        auth_text = voice.render_social_auth_required("рилс")

        self.assertIn("рилс", queue_text)
        self.assertIn("5", queue_text)
        self.assertIn("рилс", progress_text)
        self.assertIn("рилс", success_text)
        self.assertIn("https://example.com/reel", caption_text)
        self.assertIn("https://t.me/channel/1", caption_text)
        self.assertIn("boom", error_text)
        self.assertIn("/ig_login", auth_text)

        for text in (queue_text, progress_text, success_text, caption_text, error_text, auth_text):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_admin_and_instagram_templates_include_values(self) -> None:
        no_rights = voice.render_admin_no_rights()
        private_only = voice.render_admin_private_only()
        missing_args = voice.render_admin_missing_args()
        success = voice.render_admin_success()
        error = voice.render_admin_error("kaput")
        status = voice.render_instagram_status(
            InstagramAuthStatus(
                has_cookiefile=True,
                cookies_updated_at=datetime(2026, 6, 28, 12, 0, 0),
                last_test_at=datetime(2026, 6, 28, 12, 5, 0),
                last_test_ok=True,
                last_test_message="download ok",
            )
        )

        self.assertIn("администратора", no_rights)
        self.assertIn("личке", private_only)
        self.assertIn("/broadcast <текст>", missing_args)
        self.assertIn("канал", success)
        self.assertIn("kaput", error)
        self.assertIn("cookies: есть", status)
        self.assertIn("download ok", status)

        for text in (no_rights, private_only, missing_args, success, error, status):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_attachment_general_and_login_templates_include_values(self) -> None:
        queue = voice.render_attachment_queue(5)
        publish_error = voice.render_attachment_publish_error("oops")
        general_error = voice.render_general_error()
        intro = voice.render_instagram_login_intro()
        ask_password = voice.render_instagram_login_ask_password("user")
        failed = voice.render_instagram_login_failed("checkpoint")
        test_started = voice.render_instagram_test_started("https://example.com/reel")
        test_success = voice.render_instagram_test_success("download ok")
        test_error = voice.render_instagram_test_error("boom")

        self.assertIn("5", queue)
        self.assertIn("oops", publish_error)
        self.assertIn("Антихайп", general_error)
        self.assertIn("cookies.txt", intro)
        self.assertIn("Netscape", intro)
        self.assertIn("instagram.com", intro)
        self.assertIn("документом", intro)
        self.assertIn("/ig_test", intro)
        self.assertIn("user", ask_password)
        self.assertIn("checkpoint", failed)
        self.assertIn("https://example.com/reel", test_started)
        self.assertIn("download ok", test_success)
        self.assertIn("boom", test_error)

        for text in (queue, publish_error, general_error, intro, ask_password, failed, test_started, test_success, test_error):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))


if __name__ == "__main__":
    unittest.main()
