from __future__ import annotations

import re
import unittest

from panimau_bot import voice
from panimau_bot.stats import BotStats


class VoiceTests(unittest.TestCase):
    def test_render_health_includes_values_and_no_placeholders(self) -> None:
        text = voice.render_health(
            uptime="1д 2ч 3м",
            total_forwarded=7,
            cancelled=2,
            joke="тестовый рофл",
        )

        self.assertIn("1д 2ч 3м", text)
        self.assertIn("7", text)
        self.assertIn("2", text)
        self.assertIn("тестовый рофл", text)
        self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_stats_includes_counts_and_type_breakdown(self) -> None:
        stats = BotStats()
        stats.add_forward("youtube")
        stats.add_forward("photo")
        stats.add_cancel()

        text = voice.render_stats(stats)

        self.assertIn("Всего попыток: 3", text)
        self.assertIn("✅ Долетело в канал: 2", text)
        self.assertIn("❌ Слилось по дороге: 1", text)
        self.assertIn("▶️ youtube: 1", text)
        self.assertIn("📸 photo: 1", text)
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

        self.assertIn("рилс", queue_text)
        self.assertIn("5", queue_text)
        self.assertIn("рилс", progress_text)
        self.assertIn("рилс", success_text)
        self.assertIn("https://example.com/reel", caption_text)
        self.assertIn("https://t.me/channel/1", caption_text)
        self.assertIn("boom", error_text)

        for text in (queue_text, progress_text, success_text, caption_text, error_text):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_admin_templates_include_error_and_no_placeholders(self) -> None:
        no_rights = voice.render_admin_no_rights()
        missing_args = voice.render_admin_missing_args()
        success = voice.render_admin_success()
        error = voice.render_admin_error("kaput")

        self.assertIn("админ", no_rights)
        self.assertIn("/broadcast <текст>", missing_args)
        self.assertIn("канал", success)
        self.assertIn("kaput", error)

        for text in (no_rights, missing_args, success, error):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))

    def test_render_attachment_and_general_templates_include_delay_and_error(self) -> None:
        queue = voice.render_attachment_queue(5)
        publish_error = voice.render_attachment_publish_error("oops")
        general_error = voice.render_general_error()

        self.assertIn("5", queue)
        self.assertIn("oops", publish_error)
        self.assertIn("frfr", general_error)

        for text in (queue, publish_error, general_error):
            self.assertIsNone(re.search(r"\{[a-z_]+\}", text))


if __name__ == "__main__":
    unittest.main()
