from __future__ import annotations

import unittest

from panimau_bot.models import PendingStore


class PendingStoreTests(unittest.TestCase):
    def test_pop_missing_returns_default_without_error(self) -> None:
        store = PendingStore()
        sentinel = object()

        self.assertIs(store.pop("missing", sentinel), sentinel)

    def test_set_get_and_pop_roundtrip(self) -> None:
        store = PendingStore()
        post = object()

        store.set("42", post)

        self.assertIs(store.get("42"), post)
        self.assertIs(store.pop("42", None), post)
        self.assertIsNone(store.get("42"))


if __name__ == "__main__":
    unittest.main()
