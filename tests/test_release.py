from __future__ import annotations

import unittest
from pathlib import Path

from panimau_bot.release import APP_VERSION, CHANGELOG


class ReleaseTests(unittest.TestCase):
    def test_current_version_and_entries_are_in_changelog_file(self) -> None:
        changelog_file = (
            Path(__file__).resolve().parents[1] / "CHANGELOG.md"
        ).read_text(encoding="utf-8")

        self.assertIn(f"## {APP_VERSION}", changelog_file)
        self.assertTrue(CHANGELOG)
        plain_changelog = changelog_file.replace("`", "")
        for entry in CHANGELOG:
            self.assertIn(entry, plain_changelog)


if __name__ == "__main__":
    unittest.main()
