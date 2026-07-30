from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from panimau_bot.services.state import BotState


class BotStateTests(unittest.TestCase):
    def test_announcement_flag_is_scoped_to_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))

            self.assertFalse(state.has_announced("2.1.0"))
            state.mark_announced("2.1.0")

            self.assertTrue(state.has_announced("2.1.0"))
            self.assertFalse(state.has_announced("2.2.0"))

    def test_feedback_is_saved_as_jsonl_with_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))

            feedback_id = state.add_feedback(
                text="Добавьте больше света",
                user_id=42,
                username="ogre",
                full_name="Ogre Magi",
                chat_id=-100,
                chat_type="supergroup",
                message_id=7,
                bot_version="2.1.0",
            )

            record = json.loads(state.feedback_file.read_text(encoding="utf-8"))
            self.assertEqual(record["id"], feedback_id)
            self.assertEqual(record["text"], "Добавьте больше света")
            self.assertEqual(record["user"]["id"], 42)
            self.assertEqual(record["chat"]["id"], -100)
            self.assertEqual(record["bot_version"], "2.1.0")
            self.assertTrue(state.has_feedback())


if __name__ == "__main__":
    unittest.main()
