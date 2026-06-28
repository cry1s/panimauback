from __future__ import annotations

import random
from typing import TYPE_CHECKING

from panimau_bot.constants import FILE_EMOJIS

if TYPE_CHECKING:
    from panimau_bot.services.instagram_auth import InstagramAuthStatus
    from panimau_bot.stats import BotStats

HEALTH_RESPONSES = (
    "Хан Замай на месте. Аптайм стоит ровно, будто его прибили к полу баттл-стола.",
    "Антихайп-режим жив: без фанфар, зато с таким лицом, будто сервер сам попросил автограф.",
    "Бот не умер. Он просто смотрит на очередь так, как судья смотрит на слабый третий раунд.",
    "«Бытиё есть Панчлайн», а аптайм есть доказательство: процесс дышит и не делает вид.",
    "Молодой Бишкек докладывает: железо не сдалось, канал не забыт, чат под наблюдением.",
    "Я тут, как неприятный факт в чужой биографии: выключить хочется, но уже поздно.",
    "Система в строю. Логи шелестят, ffmpeg точит зубы, рилсы ждут приговора.",
    "Пока ты моргнул, я уже проверил пульс, очередь и моральное банкротство контента.",
)

TOXIC_JOKES = (
    "Это не баг, это мини-опера «Бытиё есть Панчлайн» в один traceback.",
    "Контент улетел из чата в канал так быстро, что у сомнений не загрузилась обложка.",
    "Оверхайп отменяется: сначала файл, потом уже флекс и пресс-релиз в подъезде.",
    "Твой workflow хотел стадион, но собрал кружок молчаливого уважения у /stats.",
    "Антихайп такой: не объяснять победу, а просто оставить ссылку на месте преступления.",
    "Если бы прокрастинация была баттлом, ты бы опоздал даже на собственный вылет.",
    "Этот рилс шел в канал увереннее, чем половина людей идет к дедлайну.",
    "Я не токсичный, я просто markdown с человеческим лицом и плохими новостями.",
    "Любой приватный рилс без cookies выглядит как понт без бэка: шум есть, доступа нет.",
    "Кнопка отмены существует, чтобы у слабости был официальный интерфейс.",
)

ATTACHMENT_QUEUE_TEMPLATES = (
    "Файл уже в предбаннике канала. Есть {delay_seconds} сек. на отмену, дальше начнется взрослая жизнь.",
    "Поставил вложение на рельсы. {delay_seconds} сек. на то, чтобы передумать и не изображать героя.",
    "Материал принят. Через {delay_seconds} сек. он уйдет в канал, как панч в тишину после бита.",
    "Файл стоит на отправке. {delay_seconds} сек. на стоп-кран, потом «из замка в замок».",
    "Очередь сказала «беру». У тебя {delay_seconds} сек., чтобы отменить этот культурный экспорт.",
)

ATTACHMENT_SUCCESS_TEMPLATES = (
    "Файл уже в канале. Поздравляю, он прошел путь от вложения до улики.",
    "Долетело в канал. Антихайп не хлопает, он просто ставит галочку.",
    "Готово. Контент пересек границу, паспорт не спросили.",
    "В канале. «Из замка в замок», без лишнего ресепшена.",
    "Отправлено. Теперь это уже история, а не черновик.",
)

POST_CANCELLED_TEMPLATES = (
    "Отмена принята. Контент снят с рейса, публика делает вид, что так и надо.",
    "Остановил. Антихайп победил хайп еще до выхода на сцену.",
    "Принято, не публикую. Редкий случай, когда сомнение оказалось продюсером.",
    "Отменено. Файл возвращен в подполье без пресс-конференции.",
)

SOCIAL_QUEUE_TEMPLATES = (
    "Сейчас стяну {label}. Есть {delay_seconds} сек. на отмену, потом он пойдет в канал без алиби.",
    "{label} поставлен на крюк. {delay_seconds} сек. на заднюю, дальше начнется импорт культуры.",
    "Забираю {label}. Таймер {delay_seconds} сек.; кто не отменил, тот соучастник.",
    "{label} уже в очереди. {delay_seconds} сек. на последний приступ ответственности.",
    "Поймал ссылку на {label}. Через {delay_seconds} сек. проверим, есть ли у нее характер.",
)

SOCIAL_PROGRESS_TEMPLATES = (
    "Тяну {label}. Сайт сопротивляется, но это его слабый куплет.",
    "Качаю {label}. «Бытиё есть Панчлайн», а progress bar есть нервный тик.",
    "Иду за {label}. Если Instagram опять строит дворец из checkpoint, скажу прямо.",
    "{label} в обработке. ffmpeg уже надел плащ судебного исполнителя.",
    "Достаю {label}. Сейчас станет ясно, это контент или закрытая дверь с красивой ручкой.",
)

SOCIAL_SUCCESS_TEMPLATES = (
    "{label} уже в канале. Оверхайп не понадобился, хватило холодной техники.",
    "Готово: {label} в канале, ссылка пристегнута, публика может делать серьезные лица.",
    "{label} доставлен. Из чата в канал, как панч из тетради в легенду.",
    "Вытянул {label}. Сайт делал вид, что он крепость, но там была калитка.",
    "{label} опубликован. Канал получил свою дозу странной славы.",
)

SOCIAL_ERROR_TEMPLATES = (
    "Не вытянул {label}. Сайт сделал вид, что он элитный клуб. ({error})",
    "{label} не дался. Где-то между ссылкой и реальностью начался балаган. ({error})",
    "Скачивание {label} упало. Баттл с платформой пока за платформой. ({error})",
    "Не получилось достать {label}. Это не панч, это технический отказ. ({error})",
)

SOCIAL_AUTH_REQUIRED_TEMPLATES = (
    "Instagram не отдает {label} без сессии. Админу нужно обновить /ig_login в личке.",
    "{label} спрятан за Instagram-сессией. Нужен /ig_login от админа, иначе это театр закрытых дверей.",
    "Instagram показал табличку «только своим». Админу пора в личку и /ig_login для {label}.",
)

GENERAL_ERROR_TEMPLATES = (
    "Что-то упало. Антихайп держится, traceback уже в логах.",
    "Антихайп докладывает: сцена задымилась, но виновник уже в логах.",
    "Бот споткнулся о железо реальности. Антихайп не паникует, он читает traceback.",
)


def _pick(options: tuple[str, ...]) -> str:
    return random.choice(options)


def _render(options: tuple[str, ...], **values: object) -> str:
    return _pick(options).format(**values)


def pick_joke() -> str:
    return _pick(TOXIC_JOKES)


def render_welcome() -> str:
    return (
        "Хан Замай у пульта, бот у станка.\n\n"
        "Я забираю вложения, YouTube Shorts, Instagram Reels и TikTok из группы, "
        "кидаю их в канал и даю несколько секунд на отмену. "
        "Если Instagram закрывает дверь, админ приносит cookies через /ig_login, "
        "и этот цирк снова едет.\n\n"
        "Команды:\n"
        "• /health - проверить, жив ли бот\n"
        "• /stats - посмотреть статистику\n"
        "• /joke - получить короткий панч\n"
        "• /help - показать это сообщение\n\n"
        "Админское:\n"
        "• /broadcast <текст> - отправить текст в канал\n"
        "• /ig_login - обновить Instagram cookies в личке\n"
        "• /ig_status - проверить состояние Instagram-сессии\n"
        "• /ig_test [url] - тестовый прогон Reels\n"
        "• /ig_logout - удалить Instagram cookies"
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
        f"Аптайм: {uptime}\n"
        f"В канал долетело: {total_forwarded}\n"
        f"Отменено по дороге: {cancelled}"
    )

    if joke:
        text += f"\n\nПанч:\n{joke}"

    return text


def render_tell_joke(joke: str | None = None) -> str:
    actual_joke = joke or pick_joke()
    return f"Панч на выдаче:\n{actual_joke}"


def render_empty_stats() -> str:
    return _pick(
        (
            "Статистика пустая. «Мне никогда не собрать стадион», если никто ничего не шлет.",
            "Пока нули. Канал смотрит в пустоту, как артист на афишу без даты.",
            "Стат нет: ни побед, ни отмен, только тишина с претензией на концепт.",
            "Пусто. Даже счетчик попыток отказался делать вид, что тут движ.",
        )
    )


def render_stats(stats: "BotStats") -> str:
    text = (
        "*Статы без оверхайпа:*\n\n"
        f"Аптайм: {stats.get_uptime()}\n"
        f"Всего попыток: {stats.total_attempts}\n"
        f"Долетело в канал: {stats.total_forwarded}\n"
        f"Отменено по дороге: {stats.cancelled}\n\n"
        "Разбивка по типам:"
    )

    for file_type, count in stats.by_type.items():
        emoji = FILE_EMOJIS.get(file_type, "•")
        text += f"\n{emoji} {file_type}: {count}"

    if stats.total_attempts:
        cancel_rate = (stats.cancelled / stats.total_attempts) * 100
        text += f"\n\nПроцент отмен: {cancel_rate:.1f}%"

    text += f"\n\n{_pick(('Цифры сухие, как судья после слабого панча.', 'Вот такая бухгалтерия подпольного канала.', 'Статистика сказала свое, дальше только шум.'))}"
    return text


def attachment_cancel_button_text() -> str:
    return "Отмена"


def social_cancel_button_text() -> str:
    return "Не качай"


def render_attachment_queue(delay_seconds: int) -> str:
    return _render(ATTACHMENT_QUEUE_TEMPLATES, delay_seconds=delay_seconds)


def render_attachment_success() -> str:
    return _pick(ATTACHMENT_SUCCESS_TEMPLATES)


def render_post_cancelled() -> str:
    return _pick(POST_CANCELLED_TEMPLATES)


def render_attachment_publish_error(error: object) -> str:
    return _pick(
        (
            f"Не смог отправить вложение в канал. ({error})",
            f"Вложение не прошло фейс-контроль у Telegram. ({error})",
            f"Публикация вложения развалилась в руках, как плохой концепт-альбом. ({error})",
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
            f"Лови {label}:",
            f"{label} доставлен:",
            f"Вот твой {label}, без оверхайпа:",
            f"Материал прибыл, {label} на месте:",
        )
    )
    text = f"{intro}\n{url}"
    if link:
        text += f"\n\n{link}"
    return text


def render_social_error(label: str, error: object) -> str:
    return _render(SOCIAL_ERROR_TEMPLATES, label=label, error=error)


def render_social_auth_required(label: str) -> str:
    return _render(SOCIAL_AUTH_REQUIRED_TEMPLATES, label=label)


def render_admin_no_rights() -> str:
    return _pick(
        (
            "Нет прав администратора. Это закрытый микрофон, не open mic.",
            "Нет прав администратора. Проходи мимо, тут backstage.",
            "Нет прав администратора. Пульт не трогать, он кусается.",
        )
    )


def render_admin_private_only() -> str:
    return _pick(
        (
            "Эта команда работает только в личке с ботом.",
            "В личке, пожалуйста. Секреты не читают на площади.",
            "Только в личке. Группа не место для админской кухни.",
        )
    )


def render_admin_missing_args() -> str:
    return _pick(
        (
            "Нужен текст: /broadcast <текст>",
            "Пустой broadcast - это не минимализм, это ошибка. Пиши /broadcast <текст>",
            "Дай текст после команды: /broadcast <текст>",
        )
    )


def render_admin_success() -> str:
    return _pick(
        (
            "Отправил в канал.",
            "Вкинул в канал. Слово вышло из гримерки.",
            "канал получил сообщение. Теперь оно делает вид, что всегда там было.",
        )
    )


def render_admin_error(error: object) -> str:
    return _pick(
        (
            f"Админ-команда не прошла. ({error})",
            f"Админский выстрел дал осечку. ({error})",
            f"Команда споткнулась на входе в канал. ({error})",
        )
    )


def render_instagram_login_intro() -> str:
    return (
        "Instagram login, подвальный спецвыпуск.\n\n"
        "Самый надежный путь - cookies.txt:\n"
        "1. Открой instagram.com в браузере и войди в аккаунт, с которого доступны нужные Reels.\n"
        "2. Поставь расширение или утилиту, которая экспортирует cookies в Netscape cookies.txt format.\n"
        "3. На странице instagram.com экспортируй cookies только для instagram.com, если инструмент это умеет.\n"
        "4. Проверь, что файл называется cookies.txt и внутри есть строки с instagram.com, не JSON.\n"
        "5. Пришли этот файл сюда документом, не текстом и не скрином.\n"
        "6. После сохранения запусти /ig_test на проблемном Reels.\n\n"
        "cookies.txt - это ключ от сессии: не кидай его в группу, не пересылай лишним людям, "
        "а если файл утек - выйди из Instagram-сессий в настройках аккаунта и обнови /ig_login.\n\n"
        "Запасной путь: следующим сообщением отправь username, потом password, потом 2FA-код или '-' без 2FA. "
        "Пароль не сохраняется; постоянным остается только cookie jar. Если Instagram включит checkpoint/CAPTCHA, "
        "не спорим с дверью - все равно нужен cookies.txt из браузера."
    )


def render_instagram_login_ask_password(username: str) -> str:
    return _pick(
        (
            f"Username принят: {username}. Теперь отправь password одним сообщением.",
            f"{username} записал. Давай password, только без публичного театра.",
            f"Логин {username} на столе. Следующий ход - password.",
        )
    )


def render_instagram_login_ask_twofactor() -> str:
    return _pick(
        (
            "Если есть 2FA-код, отправь его. Если нет, отправь '-'.",
            "Теперь 2FA-код. Нет кода - кидай '-', не устраиваем спиритический сеанс.",
            "Жду 2FA. Если Instagram не просил код, отправь '-'.",
        )
    )


def render_instagram_login_success(message: str) -> str:
    return _pick(
        (
            f"Instagram-сессия обновлена. {message}",
            f"Сессия Instagram на месте. Теперь приватные двери хотя бы имеют ручку. {message}",
            f"Cookie-ритуал прошел. Instagram временно делает вид, что мы свои. {message}",
        )
    )


def render_instagram_login_failed(error: object) -> str:
    return _pick(
        (
            "Instagram login не прошел. Если прилетел checkpoint/CAPTCHA, "
            f"выгрузи cookies.txt из браузера и пришли документом. ({error})",
            "Instagram включил охранника у входа. "
            f"Лучший ход - cookies.txt из браузера документом. ({error})",
            "Логин развалился на стороне Instagram. "
            f"Если это checkpoint, пароль тут не герой, нужен cookies.txt. ({error})",
        )
    )


def render_instagram_login_cancelled() -> str:
    return _pick(
        (
            "Instagram login отменен.",
            "Отбой. Instagram-сессия остается как была.",
            "Логин отменен. Дверь закрыли без скандала.",
        )
    )


def render_instagram_cookie_saved() -> str:
    return _pick(
        (
            "cookies.txt сохранен. Проверь /ig_test, прежде чем гнать приватные Reels.",
            "Cookie jar на месте. Теперь /ig_test, чтобы не верить на слово даже себе.",
            "Cookies приняты. Дальше контрольный выстрел: /ig_test.",
        )
    )


def render_instagram_cookie_error(error: object) -> str:
    return _pick(
        (
            f"cookies.txt не принят. ({error})",
            f"Cookie-файл выглядит как подделка на входе. ({error})",
            f"Не сохранил cookies: формат не прошел баттл с реальностью. ({error})",
        )
    )


def render_instagram_status(status: "InstagramAuthStatus") -> str:
    cookie_line = "есть" if status.has_cookiefile else "нет"
    updated_at = status.cookies_updated_at.isoformat(sep=" ") if status.cookies_updated_at else "никогда"

    if status.last_test_ok is None:
        test_line = "тест еще не запускался"
    else:
        result = "ok" if status.last_test_ok else "fail"
        tested_at = status.last_test_at.isoformat(sep=" ") if status.last_test_at else "неизвестно"
        test_line = f"{result} в {tested_at}: {status.last_test_message}"

    verdict = _pick(
        (
            "Вердикт: если cookies живые, рилсы пойдут строем.",
            "Сводка с передовой Instagram-дверей.",
            "Без мистики: либо есть cookies, либо платформа делает кислое лицо.",
        )
    )
    return (
        "Instagram status:\n"
        f"cookies: {cookie_line}\n"
        f"updated: {updated_at}\n"
        f"last test: {test_line}\n\n"
        f"{verdict}"
    )


def render_instagram_test_started(url: str) -> str:
    return _pick(
        (
            f"Тестирую Reels: {url}",
            f"Запускаю контрольный прогон: {url}",
            f"Проверяю, пустит ли Instagram без спектакля: {url}",
        )
    )


def render_instagram_test_success(message: str) -> str:
    return _pick(
        (
            f"Instagram test ok. {message}",
            f"Тест прошел. Instagram сегодня не строит из себя замок. {message}",
            f"Reels достается. Можно работать. {message}",
        )
    )


def render_instagram_test_error(error: object) -> str:
    return _pick(
        (
            f"Instagram test fail. ({error})",
            f"Тест Reels упал. Instagram снова изображает закрытую вечеринку. ({error})",
            f"Контрольный прогон не прошел. ({error})",
        )
    )


def render_instagram_logout(deleted: bool) -> str:
    if deleted:
        return _pick(
            (
                "Instagram cookies удалены.",
                "Cookie jar снесен. Instagram снова чужая крепость.",
                "Cookies стерты. Двери закрылись, ключи в пепельнице.",
            )
        )
    return _pick(
        (
            "Instagram cookies и так не было.",
            "Удалять нечего: cookie jar пустой, как афиша без даты.",
            "Cookies не найдены. Тут и до тебя было чисто.",
        )
    )


def render_general_error() -> str:
    return _pick(GENERAL_ERROR_TEMPLATES)
