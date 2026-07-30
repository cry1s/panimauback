from __future__ import annotations

import unittest
from types import SimpleNamespace

from panimau_bot.handlers.attachments import _collect_attachment_items


class AttachmentTests(unittest.TestCase):
    def test_animation_is_not_also_collected_as_document(self) -> None:
        message = SimpleNamespace(
            photo=None,
            video=None,
            audio=None,
            voice=None,
            animation=SimpleNamespace(file_id="gif-file"),
            document=SimpleNamespace(file_id="gif-file"),
            sticker=None,
        )

        self.assertEqual(
            _collect_attachment_items(message),
            [("animation", "gif-file")],
        )


if __name__ == "__main__":
    unittest.main()
