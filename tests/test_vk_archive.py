from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from panimau_bot.services.state import BotState
from panimau_bot.services.vk_archive import (
    ArchiveRepublisher,
    VkAttachments,
    VkAudioAttachment,
    VkPost,
    VkRepost,
    VkVideoAttachment,
    VkWallClient,
    build_post_caption,
    collect_audios,
    collect_visual_media,
)


def make_settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "vk_service_token": "token",
        "vk_source_domain": "panim4u",
        "channel_id": "@channel",
        "group_id": -100,
        "archive_trigger_posts": 3,
        "archive_min_delay_seconds": 0,
        "archive_max_delay_seconds": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_post(
    post_id: int = 1,
    text: str = "",
    attachments: VkAttachments | None = None,
    repost: VkRepost | None = None,
) -> VkPost:
    return VkPost(
        post_id=post_id,
        text=text,
        attachments=attachments if attachments is not None else VkAttachments(),
        repost=repost,
    )


class FakeJobQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[object, float]] = []

    def run_once(self, callback: object, when: float, data: object = None, name: str | None = None) -> None:
        self.jobs.append((callback, float(when)))


class StubClient(VkWallClient):
    def __init__(self, post_ids: list[int] | None = None, posts_by_id: dict[int, VkPost] | None = None) -> None:
        super().__init__("token", "panim4u")
        self.post_ids = post_ids or []
        self.posts_by_id = posts_by_id or {}

    def fetch_all_post_ids(self) -> list[int]:
        return list(self.post_ids)

    def fetch_post(self, post_id: int) -> VkPost | None:
        return self.posts_by_id.get(post_id)


class ScriptedClient(VkWallClient):
    """Возвращает заранее заготовленные ответы API вместо сетевых вызовов."""

    def __init__(self, responses: dict[str, list[object]]) -> None:
        super().__init__("token", "panim4u")
        self.responses = responses
        self.counters: dict[str, int] = {method: 0 for method in responses}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def _call(self, method: str, **params: object) -> object:
        self.calls.append((method, params))
        index = self.counters[method]
        self.counters[method] += 1
        return self.responses[method][index]


class VkArchiveHelpersTests(unittest.TestCase):
    def test_best_photo_url_picks_largest_area(self) -> None:
        photo = {
            "sizes": [
                {"width": 130, "height": 130, "url": "small"},
                {"width": 604, "height": 402, "url": "medium"},
                {"width": 1280, "height": 853, "url": "large"},
            ]
        }

        self.assertEqual(VkWallClient.best_photo_url(photo), "large")

    def test_best_photo_url_falls_back_to_fixed_sizes(self) -> None:
        self.assertEqual(VkWallClient.best_photo_url({"photo_807": "fallback"}), "fallback")
        self.assertIsNone(VkWallClient.best_photo_url({}))

    def test_video_page_url_includes_access_key(self) -> None:
        video = VkVideoAttachment(owner_id=-77, video_id=42, access_key="secret")

        self.assertEqual(video.page_url, "https://vk.com/video-77_42_secret")
        self.assertEqual(VkVideoAttachment(owner_id=-1, video_id=2).page_url, "https://vk.com/video-1_2")

    def test_audio_label_prefers_artist_and_title(self) -> None:
        self.assertEqual(VkAudioAttachment(artist="A", title="B").label, "A — B")
        self.assertEqual(VkAudioAttachment(title="B").label, "B")
        self.assertEqual(VkAudioAttachment().label, "трек")

    def test_build_post_caption_joins_text_and_repost(self) -> None:
        post = make_post(
            text="основной текст",
            repost=VkRepost(author="Старый Паблик", text="текст репоста"),
        )

        caption = build_post_caption(post)

        self.assertIn("основной текст", caption)
        self.assertIn("↪ Старый Паблик:", caption)
        self.assertIn("текст репоста", caption)

    def test_build_post_caption_omits_unresolved_media_links(self) -> None:
        post = make_post(
            text="пост",
            attachments=VkAttachments(
                videos=(VkVideoAttachment(owner_id=-77, video_id=1, title="Клип"),),
                audios=(VkAudioAttachment(artist="Группа", title="Песня"),),
            ),
        )

        caption = build_post_caption(post)

        self.assertEqual("пост", caption)
        self.assertNotIn("vk.com", caption)
        self.assertNotIn("🎥", caption)
        self.assertNotIn("🎵", caption)

    def test_build_post_caption_truncates_with_ellipsis(self) -> None:
        post = make_post(text="ж" * 5000)

        caption = build_post_caption(post, limit=100)

        self.assertLessEqual(len(caption), 100)
        self.assertTrue(caption.endswith("…"))

    def test_build_post_caption_skips_empty_repost(self) -> None:
        post = make_post(text="текст", repost=VkRepost(author="", text=""))

        self.assertEqual(build_post_caption(post), "текст")

    def test_is_empty_considers_media(self) -> None:
        empty = make_post()
        with_audio_only = make_post(attachments=VkAttachments(audios=(VkAudioAttachment(url=None),)))

        self.assertTrue(empty.is_empty)
        self.assertFalse(with_audio_only.is_empty)

    def test_collect_visual_media_merges_dedupes_and_caps(self) -> None:
        own_photos = tuple(f"u{i}" for i in range(8))
        post = make_post(
            attachments=VkAttachments(
                photo_urls=own_photos,
                videos=(
                    VkVideoAttachment(owner_id=-1, video_id=9, file_url="v9"),
                ),
            ),
            repost=VkRepost(
                author="x",
                text="",
                attachments=VkAttachments(
                    photo_urls=("u0", "r1"),
                    videos=(VkVideoAttachment(owner_id=-1, video_id=9, file_url="v9-dup"),),
                ),
            ),
        )

        photos, videos = collect_visual_media(post)

        self.assertEqual(photos[:8], own_photos)
        self.assertIn("r1", photos)
        self.assertNotIn("u0", photos[8:])
        self.assertNotIn("https://vk.com/", "".join(v.file_url or "" for v in videos))
        self.assertEqual(((-1, 9),), tuple((v.owner_id, v.video_id) for v in videos))
        self.assertLessEqual(len(photos) + len(videos), 10)

    def test_collect_visual_media_skips_videos_without_file(self) -> None:
        post = make_post(
            attachments=VkAttachments(
                videos=(VkVideoAttachment(owner_id=-1, video_id=5, file_url=None),),
                photo_urls=("p1",),
            )
        )

        photos, videos = collect_visual_media(post)

        self.assertEqual(("p1",), photos)
        self.assertEqual((), videos)

    def test_collect_audios_keeps_only_downloadable_without_duplicates(self) -> None:
        post = make_post(
            attachments=VkAttachments(
                audios=(
                    VkAudioAttachment(artist="A", title="X", url="mp3-a"),
                    VkAudioAttachment(artist="B", title="Y", url=None),
                )
            ),
            repost=VkRepost(
                author="r",
                text="",
                attachments=VkAttachments(
                    audios=(VkAudioAttachment(artist="A", title="X", url="mp3-copy"),)
                ),
            ),
        )

        audios = collect_audios(post)

        self.assertEqual(("mp3-a",), tuple(audio.url for audio in audios))

    def test_collect_audios_caps_at_ten(self) -> None:
        post = make_post(
            attachments=VkAttachments(
                audios=tuple(
                    VkAudioAttachment(artist=f"A{i}", title="t", url=f"u{i}") for i in range(15)
                )
            )
        )

        self.assertEqual(10, len(collect_audios(post)))


class VkWallClientTests(unittest.TestCase):
    def test_fetch_all_post_ids_paginates_and_filters(self) -> None:
        client = ScriptedClient(
            {
                "groups.getById": [{"groups": [{"id": 77}]}],
                "wall.get": [
                    {
                        "count": 5,
                        "items": [
                            {"id": 1, "is_pinned": 1},
                            {"id": 2, "marked_as_ads": 1},
                            {"id": 3},
                        ],
                    },
                    {"count": 5, "items": [{"id": 4}, {"id": 5}]},
                ],
            }
        )

        ids = client.fetch_all_post_ids()

        self.assertEqual([3, 4, 5], ids)
        methods = [name for name, _ in client.calls]
        self.assertIn("groups.getById", methods)
        wall_calls = [params for name, params in client.calls if name == "wall.get"]
        self.assertEqual(-77, wall_calls[0]["owner_id"])
        self.assertEqual("owner", wall_calls[0]["filter"])

    def test_build_post_parses_text_photos_and_repost(self) -> None:
        client = ScriptedClient({"groups.getById": [{"groups": [{"id": 77, "name": "Чужой Паблик"}]}]})
        item = {
            "id": 42,
            "text": "пост текст",
            "attachments": [
                {"type": "photo", "photo": {"sizes": [{"width": 5, "height": 5, "url": "ph"}]}}
            ],
            "copy_history": [
                {
                    "from_id": -45,
                    "text": "репост текст",
                    "attachments": [
                        {"type": "photo", "photo": {"sizes": [{"width": 6, "height": 6, "url": "rp"}]}}
                    ],
                }
            ],
        }

        post = client.build_post(item)

        self.assertEqual(42, post.post_id)
        self.assertEqual("пост текст", post.text)
        self.assertEqual(("ph",), post.attachments.photo_urls)
        assert post.repost is not None
        self.assertEqual("Чужой Паблик", post.repost.author)
        self.assertEqual("репост текст", post.repost.text)
        self.assertEqual(("rp",), post.repost.attachments.photo_urls)

    def test_build_attachments_resolves_video_file_via_api(self) -> None:
        client = ScriptedClient(
            {
                "video.get": [{"items": [{"files": {"mp4_240": "low", "mp4_720": "best"}}]}],
            }
        )

        attachments = client.build_attachments(
            [
                {
                    "type": "video",
                    "video": {
                        "owner_id": -77,
                        "id": 13,
                        "title": "Видео",
                        "access_key": "key",
                    },
                }
            ]
        )

        video = attachments.videos[0]
        self.assertEqual("best", video.file_url)
        self.assertEqual("Видео", video.title)
        self.assertEqual((-77, 13), (video.owner_id, video.video_id))
        self.assertEqual(("video.get", {"videos": "-77_13_key", "count": 1}), client.calls[0])

    def test_resolve_video_file_caches_and_survives_errors(self) -> None:
        class FailingThenStub(ScriptedClient):
            def __init__(self) -> None:
                super().__init__({})
                self.attempts = 0

            def _call(self, method: str, **params: object) -> object:
                self.attempts += 1
                raise RuntimeError("нет доступа")

        client = FailingThenStub()

        first = client.resolve_video_file({"owner_id": -1, "id": 2})
        second = client.resolve_video_file({"owner_id": -1, "id": 2})

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(1, client.attempts)

    def test_build_attachments_parses_audio_with_and_without_url(self) -> None:
        client = ScriptedClient({})

        attachments = client.build_attachments(
            [
                {"type": "audio", "audio": {"artist": "Кино", "title": "Пачка сигарет", "url": "http://mp3"}},
                {"type": "audio", "audio": {"title": "Без ссылки"}},
            ]
        )

        first, second = attachments.audios
        self.assertEqual(("Кино", "Пачка сигарет", "http://mp3"), (first.artist, first.title, first.url))
        self.assertIsNone(second.url)

    def test_fetch_post_returns_none_for_missing(self) -> None:
        client = ScriptedClient(
            {
                "groups.getById": [{"groups": [{"id": 77}]}],
                "wall.getById": [{"items": []}],
            }
        )

        self.assertIsNone(client.fetch_post(999))


class ArchiveRepublisherTests(unittest.TestCase):
    def test_has_pending_reflects_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            empty = ArchiveRepublisher(make_settings(), state, client=StubClient())
            self.assertFalse(empty.has_pending())

            state.write_archive_state({"queue": [1], "total": 1})
            loaded = ArchiveRepublisher(make_settings(), state, client=StubClient())
            self.assertTrue(loaded.has_pending())

    def test_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))

            first = ArchiveRepublisher(make_settings(), state, client=StubClient())
            first._queue = [7, 8]
            first._published = [5]
            first._total = 3
            first._counter = 2
            first._scheduled_at = "2026-08-26T12:00:00+00:00"
            first._save()

            second = ArchiveRepublisher(make_settings(), state, client=StubClient())

            self.assertEqual([7, 8], second._queue)
            self.assertEqual([5], second._published)
            self.assertEqual(3, second._total)
            self.assertEqual(2, second._counter)
            self.assertEqual("2026-08-26T12:00:00+00:00", second._scheduled_at)

    def test_ensure_queue_shuffles_once_and_keeps_total(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            republisher = ArchiveRepublisher(
                make_settings(),
                state,
                client=StubClient(post_ids=list(range(20))),
            )

            random.seed(1234)
            republisher.ensure_queue()
            first_order = list(republisher._queue)

            self.assertEqual(list(range(20)), sorted(first_order))
            self.assertNotEqual(list(range(20)), first_order)
            self.assertEqual((0, 20), republisher.progress)

            republisher.ensure_queue()
            self.assertEqual(first_order, republisher._queue)

    def test_register_channel_post_triggers_every_third(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [9], "published": [], "total": 1})
            republisher = ArchiveRepublisher(make_settings(), state, client=StubClient())
            job_queue = FakeJobQueue()
            context = SimpleNamespace(job_queue=job_queue)

            republisher.register_channel_post(context)
            republisher.register_channel_post(context)
            self.assertEqual(2, republisher._counter)

            republisher.register_channel_post(context)

            self.assertEqual(1, len(job_queue.jobs))
            self.assertEqual(0, republisher._counter)
            delay = job_queue.jobs[0][1]
            self.assertGreaterEqual(delay, 0)
            self.assertLessEqual(delay, 10)
            self.assertIsNotNone(republisher._scheduled_at)

            while job_queue.jobs:
                job_queue.jobs.pop()

            republisher._scheduled_at = None
            republisher.register_channel_post(context)
            republisher.register_channel_post(context)
            republisher.register_channel_post(context)

            self.assertEqual(1, len(job_queue.jobs))

    def test_register_channel_post_skips_when_scheduled_or_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [9], "total": 1, "scheduled_at": "x"})
            scheduled = ArchiveRepublisher(make_settings(), state, client=StubClient())
            scheduled.register_channel_post(SimpleNamespace(job_queue=FakeJobQueue()))
            self.assertEqual(0, scheduled._counter)

            disabled = ArchiveRepublisher(
                make_settings(vk_service_token=""),
                BotState(Path(temporary_dir)),
                client=StubClient(),
            )
            disabled_job_queue = FakeJobQueue()
            disabled.register_channel_post(SimpleNamespace(job_queue=disabled_job_queue))
            self.assertEqual([], disabled_job_queue.jobs)


class EnsureQueueJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_until_success(self) -> None:
        from panimau_bot.services.vk_archive import ensure_queue_job

        class FailingThenOkClient(StubClient):
            def __init__(self) -> None:
                super().__init__()
                self.attempts = 0

            def fetch_all_post_ids(self) -> list[int]:
                self.attempts += 1
                if self.attempts < 2:
                    raise RuntimeError("vk down")
                return [1, 2, 3]

        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            archive = ArchiveRepublisher(
                make_settings(vk_service_token="token", archive_trigger_posts=3),
                state,
                client=FailingThenOkClient(),
            )
            job_queue = FakeJobQueue()
            services = SimpleNamespace(archive=archive)
            context = SimpleNamespace(
                application=SimpleNamespace(bot_data={"services": services}),
                job_queue=job_queue,
            )

            await ensure_queue_job(context)
            self.assertEqual(0, archive._total)
            self.assertEqual(1, len(job_queue.jobs))

            await ensure_queue_job(context)
            self.assertEqual(3, archive._total)
            self.assertEqual(1, len(job_queue.jobs))

    async def test_skips_when_disabled(self) -> None:
        from panimau_bot.services.vk_archive import ensure_queue_job

        with tempfile.TemporaryDirectory() as temporary_dir:
            archive = ArchiveRepublisher(
                make_settings(vk_service_token=""),
                BotState(Path(temporary_dir)),
                client=StubClient(),
            )
            job_queue = FakeJobQueue()
            services = SimpleNamespace(archive=archive)
            context = SimpleNamespace(
                application=SimpleNamespace(bot_data={"services": services}),
                job_queue=job_queue,
            )

            await ensure_queue_job(context)
            self.assertEqual(0, len(job_queue.jobs))


class ArchivePublishTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_scheduled_posts_full_text_post(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5, 6], "total": 2})
            post = make_post(post_id=5, text="старый пост")
            republisher = ArchiveRepublisher(
                make_settings(archive_trigger_posts=1),
                state,
                client=StubClient(posts_by_id={5: post}),
            )
            bot = SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock())
            job_queue = FakeJobQueue()
            context = SimpleNamespace(bot=bot, job_queue=job_queue)

            await republisher.publish_scheduled(context)

            self.assertEqual(2, bot.send_message.await_count)
            chat_ids = {call.args[0] for call in bot.send_message.await_args_list}
            self.assertEqual({"@channel", -100}, chat_ids)
            self.assertTrue(
                all(call.args[1] == "старый пост" for call in bot.send_message.await_args_list)
            )
            self.assertEqual([6], republisher._queue)
            self.assertEqual([5], republisher._published)
            self.assertEqual((1, 2), republisher.progress)
            self.assertEqual(1, len(job_queue.jobs))

    async def test_publish_scheduled_manual_skips_reschedule(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5], "total": 1})
            post = make_post(post_id=5, text="ручной пост")
            republisher = ArchiveRepublisher(
                make_settings(archive_trigger_posts=1),
                state,
                client=StubClient(posts_by_id={5: post}),
            )
            bot = SimpleNamespace(send_message=AsyncMock())
            job_queue = FakeJobQueue()
            context = SimpleNamespace(bot=bot, job_queue=job_queue)

            await republisher.publish_scheduled(context, schedule_next=False)

            self.assertEqual(0, len(job_queue.jobs))
            self.assertEqual([5], republisher._published)

    async def test_publish_scheduled_skips_on_unresolved_video(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5], "total": 1})
            post = make_post(
                post_id=5,
                text="пост с видео",
                attachments=VkAttachments(
                    videos=(VkVideoAttachment(owner_id=-77, video_id=1, title="Клип"),),
                ),
            )
            republisher = ArchiveRepublisher(
                make_settings(archive_trigger_posts=1),
                state,
                client=StubClient(posts_by_id={5: post}),
            )
            bot = SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock())
            job_queue = FakeJobQueue()
            context = SimpleNamespace(bot=bot, job_queue=job_queue)

            await republisher.publish_scheduled(context)

            bot.send_message.assert_not_awaited()
            bot.send_media_group.assert_not_awaited()
            self.assertEqual([5], republisher._published)
            self.assertEqual([], republisher._queue)
            self.assertEqual(0, len(job_queue.jobs))

    async def test_publish_scheduled_skips_on_download_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5], "total": 1})
            post = make_post(
                post_id=5,
                text="пост с видео",
                attachments=VkAttachments(
                    videos=(
                        VkVideoAttachment(owner_id=-77, video_id=1, title="Клип", file_url="http://127.0.0.1:1/x.mp4"),
                    ),
                ),
            )
            republisher = ArchiveRepublisher(
                make_settings(archive_trigger_posts=1),
                state,
                client=StubClient(posts_by_id={5: post}),
            )
            bot = SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock())
            job_queue = FakeJobQueue()
            context = SimpleNamespace(bot=bot, job_queue=job_queue)

            await republisher.publish_scheduled(context)

            bot.send_message.assert_not_awaited()
            bot.send_media_group.assert_not_awaited()
            self.assertEqual([5], republisher._published)
            self.assertEqual([], republisher._queue)

    async def test_publish_scheduled_requeues_on_failure(self) -> None:
        class BrokenClient(StubClient):
            def fetch_post(self, post_id: int) -> VkPost | None:
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5], "total": 1})
            republisher = ArchiveRepublisher(
                make_settings(),
                state,
                client=BrokenClient(posts_by_id={}),
            )
            context = SimpleNamespace(bot=SimpleNamespace(), job_queue=FakeJobQueue())

            await republisher.publish_scheduled(context)

            self.assertEqual([5], republisher._queue)
            self.assertEqual([], republisher._published)
            self.assertIsNone(republisher._scheduled_at)

    async def test_resume_pending_schedule_restores_delay(self) -> None:
        from datetime import UTC, datetime, timedelta

        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
            state.write_archive_state({"queue": [1], "total": 1, "scheduled_at": future})

            republisher = ArchiveRepublisher(make_settings(), state, client=StubClient())
            delay = republisher.resume_pending_schedule()

            self.assertIsNotNone(delay)
            assert delay is not None
            self.assertAlmostEqual(7200, delay, delta=30)

    async def test_publish_scheduled_downloads_media_groups(self) -> None:
        from unittest.mock import patch

        import panimau_bot.services.vk_archive as vk_archive_module

        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [3], "total": 1})
            payload = b"data"

            def fake_fetch_to(target: Path, url: str) -> Path | None:
                target.write_bytes(payload)
                return target

            post = make_post(
                post_id=3,
                text="медиа пост",
                attachments=VkAttachments(
                    photo_urls=("http://photo",),
                    videos=(VkVideoAttachment(owner_id=-1, video_id=1, file_url="http://clip"),),
                    audios=(VkAudioAttachment(artist="A", title="T", url="http://track"),),
                ),
            )
            republisher = ArchiveRepublisher(
                make_settings(),
                state,
                client=StubClient(posts_by_id={3: post}),
            )
            bot = SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock())
            context = SimpleNamespace(bot=bot, job_queue=FakeJobQueue())

            with patch.object(republisher, "_fetch_to", side_effect=fake_fetch_to):
                with patch.object(
                    vk_archive_module.shutil,
                    "rmtree",
                    lambda *args, **kwargs: None,
                ):
                    await republisher.publish_scheduled(context)

            self.assertFalse(bot.send_message.await_count)
            self.assertEqual(4, bot.send_media_group.await_count)

            delivered_chats = {call.args[0] for call in bot.send_media_group.await_args_list}
            self.assertEqual({"@channel", -100}, delivered_chats)

            visual_calls = [
                call for call in bot.send_media_group.await_args_list
                if [type(item).__name__ for item in call.kwargs["media"]]
                == ["InputMediaPhoto", "InputMediaVideo"]
            ]
            audio_calls = [
                call for call in bot.send_media_group.await_args_list
                if [type(item).__name__ for item in call.kwargs["media"]]
                == ["InputMediaAudio"]
            ]
            self.assertEqual(2, len(visual_calls))
            self.assertEqual(2, len(audio_calls))
            self.assertEqual("медиа пост", visual_calls[0].kwargs["media"][0].caption)
            self.assertEqual([], republisher._queue)
            self.assertEqual([3], republisher._published)


class VkDiagnoseTests(unittest.TestCase):
    def test_diagnose_reports_token_failure(self) -> None:
        class FailingClient(VkWallClient):
            def _call(self, method: str, **params: object) -> object:
                raise RuntimeError("VK API users.get: User authorization failed")

        client = FailingClient("token", "panim4u")

        result = client.diagnose()

        self.assertFalse(result["ok"])
        self.assertIn("User authorization failed", str(result["error"]))

    def test_diagnose_reports_missing_group(self) -> None:
        client = ScriptedClient(
            {
                "users.get": [[]],
                "groups.getById": [{"groups": []}],
            }
        )

        result = client.diagnose()

        self.assertFalse(result["ok"])
        self.assertIn("panim4u", str(result["error"]))

    def test_diagnose_reports_success(self) -> None:
        client = ScriptedClient(
            {
                "users.get": [[{"id": 1, "first_name": "A", "last_name": "B"}]],
                "groups.getById": [{"groups": [{"id": 77, "name": "Панимау"}]}],
                "wall.get": [{"count": 42, "items": []}],
            }
        )

        result = client.diagnose()

        self.assertTrue(result["ok"])
        self.assertEqual("Панимау", result["group_name"])
        self.assertEqual(77, result["group_id"])
        self.assertEqual(42, result["wall_posts"])


class VkArchiveNowCommandTests(unittest.IsolatedAsyncioTestCase):
    def _make_services(self, archive: object, admin_ids: tuple[int, ...] = (1,)) -> SimpleNamespace:
        settings = SimpleNamespace(admin_ids=admin_ids, group_id=-100, vk_service_token="token")
        return SimpleNamespace(archive=archive, settings=settings)

    async def _build_context(self, services: object, job_queue: object = None) -> SimpleNamespace:
        return SimpleNamespace(
            application=SimpleNamespace(bot_data={"services": services}),
            bot=SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock()),
            job_queue=job_queue or FakeJobQueue(),
        )

    async def test_requires_private_chat(self) -> None:
        from telegram.constants import ChatType
        from unittest.mock import patch

        from panimau_bot.handlers.commands import vk_archive_now

        services = self._make_services(None)
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type=ChatType.GROUP, id=-100),
            effective_user=SimpleNamespace(id=1),
            message=message,
        )

        with patch("panimau_bot.voice.render_admin_private_only") as private_only, patch(
            "panimau_bot.voice.render_admin_no_rights"
        ) as no_rights, patch("panimau_bot.voice.render_vk_diagnostic_no_token") as no_token:
            await vk_archive_now(update, await self._build_context(services))

        private_only.assert_called_once()
        no_rights.assert_not_called()
        no_token.assert_not_called()

    async def test_requires_admin(self) -> None:
        from telegram.constants import ChatType
        from unittest.mock import patch

        from panimau_bot.handlers.commands import vk_archive_now

        archive = ArchiveRepublisher(
            make_settings(vk_service_token="token"),
            BotState(Path(tempfile.mkdtemp())),
            client=StubClient(),
        )
        services = self._make_services(archive, admin_ids=(7,))
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type=ChatType.PRIVATE, id=-100),
            effective_user=SimpleNamespace(id=999),
            message=message,
        )

        with patch("panimau_bot.voice.render_admin_no_rights") as no_rights, patch(
            "panimau_bot.voice.render_admin_private_only"
        ) as private_only, patch("panimau_bot.voice.render_vk_diagnostic_no_token") as no_token, patch(
            "panimau_bot.voice.render_vk_archive_now_ok"
        ) as now_ok, patch("panimau_bot.voice.render_vk_archive_empty") as empty:
            await vk_archive_now(update, await self._build_context(services))

        no_rights.assert_called_once()
        private_only.assert_not_called()
        no_token.assert_not_called()
        now_ok.assert_not_called()
        empty.assert_not_called()

    async def test_publishes_immediately_without_rescheduling(self) -> None:
        from telegram.constants import ChatType
        from unittest.mock import patch

        from panimau_bot.handlers.commands import vk_archive_now

        with tempfile.TemporaryDirectory() as temporary_dir:
            state = BotState(Path(temporary_dir))
            state.write_archive_state({"queue": [5], "total": 1})
            post = make_post(post_id=5, text="секретный пост")
            archive = ArchiveRepublisher(
                make_settings(archive_trigger_posts=1),
                state,
                client=StubClient(posts_by_id={5: post}),
            )
            services = self._make_services(archive)
            job_queue = FakeJobQueue()
            message = SimpleNamespace(reply_text=AsyncMock())
            update = SimpleNamespace(
                effective_chat=SimpleNamespace(type=ChatType.PRIVATE, id=-100),
                effective_user=SimpleNamespace(id=1),
                message=message,
            )

            with patch("panimau_bot.voice.render_vk_archive_now_ok") as now_ok, patch(
                "panimau_bot.voice.render_vk_diagnostic_no_token"
            ) as no_token, patch("panimau_bot.voice.render_admin_no_rights") as no_rights, patch(
                "panimau_bot.voice.render_admin_private_only"
            ) as private_only, patch("panimau_bot.voice.render_vk_archive_empty") as empty:
                await vk_archive_now(update, await self._build_context(services, job_queue))

            now_ok.assert_called_once()
            no_token.assert_not_called()
            no_rights.assert_not_called()
            private_only.assert_not_called()
            empty.assert_not_called()
            self.assertEqual([], archive._queue)
            self.assertEqual([5], archive._published)
            self.assertEqual(0, len(job_queue.jobs))


if __name__ == "__main__":
    unittest.main()
