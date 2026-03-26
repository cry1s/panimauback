from __future__ import annotations

import random
from typing import TYPE_CHECKING

from panimau_bot.constants import FILE_EMOJIS

if TYPE_CHECKING:
    from panimau_bot.stats import BotStats

HEALTH_RESPONSES = (
    "🤬 Я живой, bro, frfr. Ты думал я скипнул реальность? deadass нет.",
    "🛠 Пашу как проклятый, no cap. А ты опять чекаешь /health как будто я NPC.",
    "📡 На линии, bro. У тебя мозг AFK, а я всё ещё locked in.",
    "🔥 Я тут, type shi. Не сдох, не отменился, не расплакался.",
    "🥀 Да живой я, deadass. Спрашиваешь это чаще, чем делаешь что-то полезное.",
    "💀 В строю, bro. Я ебашу, а ты опять смотришь, не откинулся ли я.",
    "😤 Тут я, no cap. Бот alive, а вот твоя дисциплина уже в obituary.",
)

TOXIC_JOKES = (
    "Твой productivity arc умер быстрее, чем ты дописал сообщение, frfr.",
    "Ты не ленивый, bro. Ты просто в eternal loading screen, no cap.",
    "Если бы прокрастинация была олимпийкой, ты бы и туда опоздал, deadass.",
    "Ты не бездарь, конечно. Просто every update makes it look worse, type shi.",
    "Твой контент не плохой, bro. Он просто звучит так, будто его писал человек без сна и души.",
    "Ты жмёшь /stats так часто, будто цифры внезапно перестанут тебя позорить.",
    "Даже мои ошибки выглядят собраннее, чем твой workflow, frfr.",
)


def pick_joke() -> str:
    return random.choice(TOXIC_JOKES)


def render_welcome() -> str:
    return (
        "💀 Yo, bro.\n\n"
        "Я тот самый бот, который пихает твои вложения, шортсы, рилсы и тиктоки в канал, "
        "потому что сам ты, deadass, опять всё проебал.\n\n"
        "Чё умею, type shi:\n"
        "• Пуляю в канал фотки, видосы и прочий стафф\n"
        "• Стягиваю YouTube Shorts, Instagram Reels и TikTok по ссылке\n"
        "• Даю тебе время слиться: 5 сек на отмену, frfr\n"
        "• Считаю, сколько раз ты фамблишь и сколько всё-таки долетело\n\n"
        "Команды, bro:\n"
        "• /health - чекнуть, не отлетел ли я\n"
        "• /stats - посмотреть свои статы без самообмана\n"
        "• /joke - получить рофл по ебалу, no cap\n"
        "• /help - если опять memory leak в голове\n\n"
        "🥀 Всё, дальше сам. Не спамь тупыми вопросами, frfr."
    )


def render_help() -> str:
    return render_welcome()


def render_health(
    uptime: str,
    total_forwarded: int,
    cancelled: int,
    joke: str | None = None,
) -> str:
    text = (
        f"{random.choice(HEALTH_RESPONSES)}\n\n"
        f"⏱ Аптайм: {uptime}\n"
        f"📤 Закинул в канал: {total_forwarded}\n"
        f"❌ Слил по дороге: {cancelled}"
    )

    if joke:
        text += f"\n\n💭 Бонусный рофл, bro:\n{joke}"

    return text


def render_tell_joke(joke: str | None = None) -> str:
    actual_joke = joke or pick_joke()
    return f"💀 Лови рофл, bro:\n{actual_joke}"


def render_empty_stats() -> str:
    return "📊 Пусто, bro. Ты ещё даже ничего не закинул, deadass тишина 🥀"


def render_stats(stats: "BotStats") -> str:
    text = (
        "📊 *Твои статы, bro frfr:*\n\n"
        f"⏱ Аптайм: {stats.get_uptime()}\n"
        f"📦 Всего попыток: {stats.total_attempts}\n"
        f"✅ Долетело в канал: {stats.total_forwarded}\n"
        f"❌ Слилось по дороге: {stats.cancelled}\n\n"
        "📁 Развал по типам:"
    )

    for file_type, count in stats.by_type.items():
        emoji = FILE_EMOJIS.get(file_type, "📎")
        text += f"\n{emoji} {file_type}: {count}"

    if stats.total_attempts:
        cancel_rate = (stats.cancelled / stats.total_attempts) * 100
        text += f"\n\n🎯 Процент очка: {cancel_rate:.1f}%"

    return text


def attachment_cancel_button_text() -> str:
    return "❌ стопни это frfr"


def social_cancel_button_text() -> str:
    return "❌ не качай, bro"


def render_attachment_queue(delay_seconds: int) -> str:
    return (
        f"🛑 Ща пульну твой файл в канал, bro. У тебя {delay_seconds} сек, "
        "чтобы дать заднюю frfr."
    )


def render_attachment_success() -> str:
    return "✅ Уже в канале, bro. Жать назад поздно, deadass."


def render_post_cancelled() -> str:
    return "❌ Ладно, отмена. Слился как classic clown, bro 🥀"


def render_attachment_publish_error(error: object) -> str:
    return f"❌ Не смог закинуть это дерьмо в канал, no cap. ({error})"


def render_social_queue(label: str, delay_seconds: int) -> str:
    return (
        f"📥 Ща стяну твой {label}, bro. У тебя {delay_seconds} сек на дать заднюю, "
        "потом оно улетит frfr."
    )


def render_social_progress(label: str) -> str:
    return f"⏳ Тяну твой {label}, не дёргайся, deadass процесс идёт."


def render_social_success(label: str) -> str:
    return f"✅ {label} уже в канале, bro. type shi done."


def render_social_reply_caption(label: str, url: str, link: str) -> str:
    text = f"✅ Лови свой {label}, no cap:\n{url}"
    if link:
        text += f"\n\n{link}"
    return text


def render_social_error(label: str, error: object) -> str:
    return f"❌ Не вытянул твой {label}, сайт выебнулся first. ({error})"


def render_admin_no_rights() -> str:
    return "🚫 Не-а, bro. Ты не админ, так что сиди ровно frfr."


def render_admin_missing_args() -> str:
    return "📝 Ты текст забыл, genius. Пиши так: /broadcast <текст>, no cap."


def render_admin_success() -> str:
    return "✅ Вкинул в канал, no cap. Теперь все это видят, type shi."


def render_admin_error(error: object) -> str:
    return f"❌ Всё разъебалось, bro. ({error})"


def render_general_error() -> str:
    return "💥 Всё ебнулось, bro. Я чутка отлетел, но ты держись frfr 🥀"
