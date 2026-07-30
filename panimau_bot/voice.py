from __future__ import annotations

import random
from typing import TYPE_CHECKING, Sequence

from panimau_bot.constants import FILE_EMOJIS

if TYPE_CHECKING:
    from panimau_bot.stats import BotStats

HEALTH_RESPONSES = (
    "Левая голова сверила пульс, правая поставила печать Сил Света: агрегат жив.",
    "Контракт сияет, котел греется, обе головы на службе. Иногда даже одновременно.",
    "Огр-маги на посту. Один следит за сервером, второй дегустирует служебный майонез.",
    "Силы Света запросили отчет. Мы ответили двумя голосами: все работает.",
    "Башня стоит, бот дышит, ложка в банке. Признаков конца света не обнаружено.",
    "Одна голова сказала «аптайм», вторая поняла «обед». Но проверку мы прошли.",
)

CONTRACT_JOKES = (
    "Мы не ошиблись адресом: просто левая голова кастовала в канал, а правая читала документацию.",
    "У огр-магов два мнения и один продакшен. Поэтому решение всегда единогласное.",
    "Силы Света платят нам за интеллект. В договоре не уточнили, чей именно.",
    "Майонез признан легендарным. Комиссия из двух голов воздержалась от воздержания.",
    "Любая проблема делится на две: ту, которую не понял первый, и ту, которую уже усугубил второй.",
    "Мы не тормозим. Мы проводим двойную проверку реальности с перерывом на соус.",
    "Один огр нажал кнопку. Второй подтвердил, что это была кнопка. Процесс считается аттестованным.",
    "Контент годен к службе в канале. Послевкусие мемное, кислотность в пределах патча.",
)

ATTACHMENT_QUEUE_TEMPLATES = (
    "Обе головы приняли вложение на светлую службу. Через {delay_seconds} сек. отправим в канал, если не отзовешь контракт.",
    "Материал лежит на алтаре логистики. У тебя {delay_seconds} сек. на отмену, у нас одна кнопка и два специалиста.",
    "Силы Света выдали накладную. Через {delay_seconds} сек. вложение уйдет в канал под двойной подписью.",
    "Левая голова держит файл, правая считает {delay_seconds} сек. до отправки. Не спрашивай, кто умеет считать.",
    "Вложение прошло дегустацию. Еще {delay_seconds} сек. можно оспорить заключение огр-магической комиссии.",
)

ATTACHMENT_SUCCESS_TEMPLATES = (
    "Вложение в канале. Две головы, одна отправка, ни одной лишней церемонии.",
    "Доставили в канал по контракту Сил Света. Печать круглая, огры довольные.",
    "Готово. Материал признан светлым, съедобным и пригодным к публикации.",
    "Файл занял боевую позицию в канале. Комиссия требует майонез.",
    "Отправка завершена. Левая голова празднует, правая уверяет, что все сделала сама.",
)

POST_CANCELLED_TEMPLATES = (
    "Контракт отозван. Обе головы делают вид, что вообще не видели этот материал.",
    "Отмена принята. Силы Света вернули накладную, огры вернули ложку в банку.",
    "Публикация остановлена. Левая голова послушалась, правая записала это как свою идею.",
    "Сняли с отправки. Светлая канцелярия закрыла дело без дегустации.",
)

SOCIAL_QUEUE_TEMPLATES = (
    "Огр-маги зацепили {label}. Через {delay_seconds} сек. понесем в канал по светлому контракту.",
    "{label} принят на экспертизу. Есть {delay_seconds} сек. отменить, пока обе головы не поставили печати.",
    "Левая голова нашла {label}, правая завела таймер на {delay_seconds} сек. Дальше работает магия снабжения.",
    "Силы Света заказали {label}. Через {delay_seconds} сек. начинаем извлечение, если приказ не отзовут.",
    "{label} стоит в очереди к двум лицензированным дегустаторам. Решение через {delay_seconds} сек.",
)

SOCIAL_PROGRESS_TEMPLATES = (
    "Тянем {label}. Одна голова читает сайт, вторая угрожающе смотрит на progress bar.",
    "{label} проходит светлую экстракцию. Котел шумит строго по техническому регламенту.",
    "Добываем {label}. Платформа спорит, но у нас две головы и официальный контракт.",
    "{label} в работе. Левая голова вызвала yt-dlp, правая уже делит премию.",
)

SOCIAL_SUCCESS_TEMPLATES = (
    "{label} в канале. Огр-маги исполнили контракт и не перепутали канал с кладовой.",
    "Готово: {label} доставлен Силам Света. Двойная комиссия одобряет послевкусие.",
    "{label} опубликован. Левая голова ставит галочку, правая ставит еще одну для надежности.",
    "Добыча завершена: {label} на месте, котел цел, отчет почти правдив.",
    "{label} прошел в канал. Два специалиста, одна ссылка, ноль темной магии.",
)

SOCIAL_ERROR_TEMPLATES = (
    "Не добыли {label}. Обе головы обвиняют платформу, и на этот раз обоснованно. ({error})",
    "{label} не прошел светлую таможню. Техническое заключение комиссии: ({error})",
    "Котел погас при извлечении {label}. Силы Света получают официальный отказ: ({error})",
    "{label} сопротивлялся сильнее нашего коллективного интеллекта. Причина: ({error})",
)

GENERAL_ERROR_TEMPLATES = (
    "Светлая операция пошла темным путем. Обе головы уже изучают ошибку в логах.",
    "Котел дал осечку. Первая голова пишет отчет, вторая ищет виноватого в зеркале.",
    "Заклинание сорвалось, но контракт действует. Технические подробности отправлены в логи.",
)


def _pick(options: tuple[str, ...]) -> str:
    return random.choice(options)


def _render(options: tuple[str, ...], **values: object) -> str:
    return _pick(options).format(**values)


def pick_joke() -> str:
    return _pick(CONTRACT_JOKES)


def render_welcome() -> str:
    return (
        "Мы огр-маги медиаснабжения, подписавшие контракт с Силами Света.\n\n"
        "Две головы принимают вложения, YouTube Shorts, Instagram Reels и TikTok из беседы, "
        "дают время на отмену и доставляют добычу в канал. Сообщения в беседе тихие, "
        "публикации в канале прибывают с фанфарами.\n\n"
        "Светлые распоряжения:\n"
        "• /health - проверить котел и обе головы\n"
        "• /stats - открыть книгу поставок\n"
        "• /joke - запросить мудрость второй головы\n"
        "• /feedback <текст> - оставить жалобу или предложение\n"
        "• /version - показать версию и текущий контракт\n"
        "• /help - повторно зачитать устав\n\n"
        "Для старших по башне:\n"
        "• /broadcast <текст> - отправить объявление в канал\n"
        "• /feedback_export - выгрузить журнал обращений в личке"
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
        f"{_pick(HEALTH_RESPONSES)}\n\n"
        f"Смена длится: {uptime}\n"
        f"Поставок в канал: {total_forwarded}\n"
        f"Отозванных контрактов: {cancelled}"
    )
    if joke:
        text += f"\n\nМудрость второй головы:\n{joke}"
    return text


def render_tell_joke(joke: str | None = None) -> str:
    return f"Вторая голова получила слово:\n{joke or pick_joke()}"


def render_empty_stats() -> str:
    return _pick(
        (
            "Книга поставок пуста. Две головы дежурили, но ни одна ничего не принесла.",
            "Статистика по нулям. Силы Света пока финансируют наше выразительное ожидание.",
            "Поставок нет. Комиссия дегустирует воздух и просит продлить контракт.",
            "Считать нечего. Левая голова предлагает начать с майонеза, правая уже начала.",
        )
    )


def render_stats(stats: "BotStats") -> str:
    text = (
        "*Книга светлых поставок:*\n\n"
        f"Смена длится: {stats.get_uptime()}\n"
        f"Всего поручений: {stats.total_attempts}\n"
        f"Доставлено в канал: {stats.total_forwarded}\n"
        f"Отозвано по дороге: {stats.cancelled}\n\n"
        "Состав каравана:"
    )
    for file_type, count in stats.by_type.items():
        emoji = FILE_EMOJIS.get(file_type, "•")
        text += f"\n{emoji} {file_type}: {count}"
    if stats.total_attempts:
        cancel_rate = (stats.cancelled / stats.total_attempts) * 100
        text += f"\n\nДоля отозванных приказов: {cancel_rate:.1f}%"
    text += f"\n\n{_pick(CONTRACT_JOKES)}"
    return text


def attachment_cancel_button_text() -> str:
    return "Отозвать приказ"


def social_cancel_button_text() -> str:
    return "Погасить котел"


def render_attachment_queue(delay_seconds: int) -> str:
    return _render(ATTACHMENT_QUEUE_TEMPLATES, delay_seconds=delay_seconds)


def render_attachment_success() -> str:
    return _pick(ATTACHMENT_SUCCESS_TEMPLATES)


def render_post_cancelled() -> str:
    return _pick(POST_CANCELLED_TEMPLATES)


def render_attachment_publish_error(error: object) -> str:
    return _pick(
        (
            f"Вложение не прошло в канал. Светлая канцелярия вернула свиток: ({error})",
            f"Обе головы отправляли, Telegram не принял. Технический вердикт: ({error})",
            f"Поставка рассыпалась у ворот канала. Причина по форме ОГР-2: ({error})",
        )
    )


def render_social_queue(label: str, delay_seconds: int) -> str:
    return _render(SOCIAL_QUEUE_TEMPLATES, label=label, delay_seconds=delay_seconds)


def render_social_progress(label: str) -> str:
    return _render(SOCIAL_PROGRESS_TEMPLATES, label=label)


def render_social_success(label: str) -> str:
    return _render(SOCIAL_SUCCESS_TEMPLATES, label=label)


def render_social_reply_caption(label: str, url: str, link: str) -> str:
    intro = _pick(
        (
            f"Держи {label}, заверенный двумя головами:",
            f"Светлая поставка: {label} прибыл.",
            f"{label} прошел огр-магическую приемку:",
            f"Комиссия выдает {label} под твою ответственность:",
        )
    )
    text = f"{intro}\n{url}"
    if link:
        text += f"\n\nЗапись в летописи канала:\n{link}"
    return text


def render_social_error(label: str, error: object) -> str:
    return _render(SOCIAL_ERROR_TEMPLATES, label=label, error=error)


def render_admin_no_rights() -> str:
    return _pick(
        (
            "Твоей подписи нет в контракте старших огр-магов. Пульт остается у нас.",
            "Силы Света не выдали тебе админскую печать. Обе головы проверили.",
            "Доступ закрыт. Даже вторая голова не смогла сделать вид, что тебя знает.",
        )
    )


def render_admin_private_only() -> str:
    return _pick(
        (
            "Админский свиток принимаем только в личке. В беседе слишком много свидетелей.",
            "Приходи в личку: старшие огр-маги не размахивают архивами на площади.",
            "Эта команда служит Силам Света только в личном чате.",
        )
    )


def render_admin_missing_args() -> str:
    return _pick(
        (
            "Свиток пуст. Нужен текст: /broadcast <текст>",
            "Даже две головы не прочитают пустоту. Формат: /broadcast <текст>",
            "Силы Света требуют содержание после /broadcast <текст>",
        )
    )


def render_admin_success() -> str:
    return _pick(
        (
            "Объявление доставлено в канал под светлой печатью.",
            "Канал получил свиток. Обе головы подтверждают отправку.",
            "Админский приказ исполнен. Фанфары оставили каналу.",
        )
    )


def render_admin_error(error: object) -> str:
    return _pick(
        (
            f"Админский приказ не прошел через ворота канала. ({error})",
            f"Светлая печать треснула при отправке. ({error})",
            f"Обе головы расписались, но доставка все равно сорвалась. ({error})",
        )
    )


def render_changelog(version: str, entries: Sequence[str]) -> str:
    changes = "\n".join(f"• {entry}" for entry in entries)
    return (
        f"Контракт огр-магов обновлен до версии {version}.\n\n"
        f"{changes}\n\n"
        "Силы Света приняли работы. Обе головы почему-то получили одну зарплату."
    )


def render_version(version: str, entries: Sequence[str]) -> str:
    changes = "\n".join(f"• {entry}" for entry in entries)
    return (
        f"Текущая редакция светлого контракта: {version}\n\n"
        f"{changes}"
    )


def render_feedback_missing() -> str:
    return _pick(
        (
            "После команды нужен текст: /feedback <жалоба или предложение>",
            "Свиток пуст. Напиши /feedback и то, что обеим головам стоит узнать.",
            "Мы готовы записать мнение, но его нет. Формат: /feedback <текст>",
        )
    )


def render_feedback_saved(feedback_id: str) -> str:
    return _pick(
        (
            f"Обращение {feedback_id} внесено в светлую книгу жалоб. Ни одна голова не сможет отвертеться.",
            f"Записали под номером {feedback_id}. Первая голова обещает прочитать, вторая назначена свидетелем.",
            f"Свиток {feedback_id} сохранен. Силы Света теперь официально в курсе твоего мнения.",
        )
    )


def render_feedback_empty() -> str:
    return _pick(
        (
            "Книга обращений пуста. Либо все идеально, либо никто не нашел /feedback.",
            "В архиве ни одной жалобы. Обе головы считают это подозрительным.",
            "Выгружать нечего: светлая книга предложений пока чиста.",
        )
    )


def render_feedback_export_caption() -> str:
    return "Полная книга жалоб и предложений. JSONL, одна строка — один официальный свиток."


def render_feedback_error(error: object) -> str:
    return _pick(
        (
            f"Не смогли записать обращение. Книга захлопнулась: ({error})",
            f"Светлая канцелярия временно не принимает свитки. ({error})",
            f"Обе головы услышали, но хранилище отказалось. ({error})",
        )
    )


def render_general_error() -> str:
    return _pick(GENERAL_ERROR_TEMPLATES)
