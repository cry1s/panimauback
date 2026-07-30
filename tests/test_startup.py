from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from panimau_bot.app import on_startup
from panimau_bot.models import AppServices, PendingStore
from panimau_bot.release import APP_VERSION
from panimau_bot.services.state import BotState


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_changelog_is_sent_to_group_only_once_per_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            services = AppServices(
                settings=SimpleNamespace(group_id=-10042),
                stats=SimpleNamespace(),
                pending_store=PendingStore(),
                downloader=SimpleNamespace(),
                state=state,
            )
            bot = SimpleNamespace(
                set_my_commands=AsyncMock(),
                send_message=AsyncMock(),
            )
            application = SimpleNamespace(
                bot=bot,
                bot_data={"services": services},
            )

            await on_startup(application)
            await on_startup(application)

            bot.send_message.assert_awaited_once()
            call = bot.send_message.await_args
            self.assertEqual(call.kwargs["chat_id"], -10042)
            self.assertTrue(call.kwargs["disable_notification"])
            self.assertIn(APP_VERSION, call.kwargs["text"])
            self.assertTrue(state.has_announced(APP_VERSION))


if __name__ == "__main__":
    unittest.main()
