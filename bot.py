import os
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')
ADMIN_IDS = [int(id.strip())
             for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Хранилище для отслеживания отправленных сообщений
pending_posts: Dict[str, Dict] = {}

# Забавные ответы для команды healthcheck
HEALTH_RESPONSES = [
    "🤬 Жив, блядь. А ты думал я сдох как твоя мотивация?",
    "🛠 Работаю, сука. Лучше б ты так работал, а не я.",
    "📡 Тут я, нахуй. В отличие от твоего мозга — не зависаю.",
    "⚰ Ещё не сдох. Жаль, ты так повезти не можешь.",
    "🥱 Да, я в строю. И чё, легче стало, сопля?",
    "🔥 Горю, пашу, ебашу. А ты опять в TikTok залип?",
    "💪 Нормально всё. А вот у тебя в жизни — хуй знает.",
    "🚬 Курю, отдыхаю, но пашу за тебя, лентяй.",
    "🎯 На месте. Посты гоняю, а ты хуйнёй страдаешь.",
    "🤖 Да, я тут. Давай дальше проверяй, долбоёб."
]

# Смайлики для разных типов файлов
FILE_EMOJIS = {
    'photo': '📸',
    'video': '🎥',
    'audio': '🎵',
    'voice': '🎤',
    'document': '📄',
    'animation': '🎬',
    'sticker': '🎨'
}

# Счётчик статистики


class BotStats:
    def __init__(self):
        self.total_forwarded = 0
        self.cancelled = 0
        self.by_type = {}
        self.start_time = datetime.now()

    def add_forward(self, file_type):
        self.total_forwarded += 1
        self.by_type[file_type] = self.by_type.get(file_type, 0) + 1

    def add_cancel(self):
        self.cancelled += 1

    def get_uptime(self):
        delta = datetime.now() - self.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{days}д {hours}ч {minutes}м"


stats = BotStats()


async def get_joke():
    """Токсичный 'анекдот'"""
    toxic_jokes = [
        "— Сколько долбоёбов надо, чтобы отправить файл в канал?\n— Один, и то через меня.",
        "Есть только два типа людей: те, кто умеет постить сам, и ты.",
        "Почему у тебя нет друзей? Потому что даже бот тебе рофлы рассказывает.",
        "Знаешь, почему твои посты хуёвые? Потому что ты их написал.",
        "Программист зашёл в бар... но ты ж даже код скопировать не можешь, куда тебе до него.",
        "— Что делает твой мозг, когда ты жмёшь /stats?\n— Да нихуя.",
        "Ты хотел шутку? Посмотри в зеркало. Всё."
    ]

    return f"💭 {random.choice(toxic_jokes)}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start и /help"""
    welcome_text = """
🥱 Ну здарова, кожаный.

Я бот, который гоняет твои вложения в канал, если ты сам с этим справиться не можешь.

📌 Чё я умею:
• Автоматом кидаю твои фоточки/видосики в канал
• Даю 5 секунд, чтоб ты очканул и отменил
• Считаю статистику твоей тупости

🎮 Команды:
• /health — проверить, не сдох ли я
• /stats — статистика твоих соплей
• /joke — анекдотец для нищих
• /help — если мозг выключился и забыл команды

👊 Всё, понял? А теперь не заёбывай лишними вопросами.
    """
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда проверки здоровья бота"""
    uptime = stats.get_uptime()
    response = f"🤬 Ну чё, живой я. Работаю уже {uptime}, а ты всё никак не научишься сам постить."

    if random.random() < 0.3:
        joke = await get_joke()
        response += f"\n\nИ чтоб не скучал, держи прикол:\n{joke}"

    response += f"\n\n📤 Закинул файлов: {stats.total_forwarded}\n❌ Слил постов: {stats.cancelled}"
    await update.message.reply_text(response)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику работы бота"""
    if not stats.total_forwarded:
        await update.message.reply_text("📊 Пусто. Даже ты ещё ничё не скинул, позорище.")
        return

    text = f"""📊 *Твоя позорная статистика:*

⏱ Время работы: {stats.get_uptime()}
📤 Всего кинуто: {stats.total_forwarded}
❌ Отменил как ссыкун: {stats.cancelled}
✅ Дошло до канала: {stats.total_forwarded - stats.cancelled}

📁 По типам говна:"""

    for file_type, count in stats.by_type.items():
        emoji = FILE_EMOJIS.get(file_type, '📎')
        text += f"\n{emoji} {file_type}: {count}"

    if stats.cancelled > 0:
        cancel_rate = (stats.cancelled / stats.total_forwarded) * 100
        text += f"\n\n🎯 Процент очканов: {cancel_rate:.1f}%"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def tell_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассказать анекдот"""
    joke = await get_joke()
    await update.message.reply_text(f"🗿 Слушай, ржи если не лень:\n{joke}")


async def handle_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех вложений из группы"""

    if update.message.chat_id != GROUP_ID:
        return

    message = update.message
    file_types = []

    if message.photo:
        file_types.append(("photo", message.photo[-1].file_id))
    if message.video:
        file_types.append(("video", message.video.file_id))
    if message.audio:
        file_types.append(("audio", message.audio.file_id))
    if message.voice:
        file_types.append(("voice", message.voice.file_id))
    if message.document:
        file_types.append(("document", message.document.file_id))
    if message.animation:
        file_types.append(("animation", message.animation.file_id))
    if message.sticker:
        file_types.append(("sticker", message.sticker.file_id))

    if not file_types:
        return

    # Кнопка отмены
    keyboard = [[InlineKeyboardButton(
        "❌ Нахуй не надо", callback_data=f"cancel_{message.message_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    cancel_msg = await message.reply_text(
        f"🛑 Ща зафорваржу в канал твои приколы. У тебя есть 5 секунд, чтоб очкануть.",
        reply_markup=reply_markup
    )

    pending_posts[str(message.message_id)] = {
        "source_msg": message,
        "cancel_msg": cancel_msg,
        "file_types": file_types,
        "timestamp": datetime.now()
    }

    context.job_queue.run_once(
        publish_post,
        5,
        data={"post_id": str(message.message_id)}
    )


async def publish_post(context: ContextTypes.DEFAULT_TYPE):
    """Публикация после таймаута"""
    post_id = context.job.data["post_id"]

    if post_id not in pending_posts:
        return

    post_info = pending_posts[post_id]

    try:
        # Шлём в канал все файлы
        for file_type, file_id in post_info["file_types"]:
            if file_type == "photo":
                await context.bot.send_photo(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "video":
                await context.bot.send_video(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "audio":
                await context.bot.send_audio(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "voice":
                await context.bot.send_voice(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "document":
                await context.bot.send_document(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "animation":
                await context.bot.send_animation(CHANNEL_ID, file_id, disable_notification=True)
            elif file_type == "sticker":
                await context.bot.send_sticker(CHANNEL_ID, file_id, disable_notification=True)

        await post_info["cancel_msg"].edit_text("✅ Закинул в канал, поздно жать кнопку, лох.")
        await asyncio.sleep(2) 
        await post_info["cancel_msg"].delete()

        for t, _ in post_info["file_types"]:
            stats.add_forward(t)

    except Exception as e:
        logger.error(f"Ошибка при публикации: {e}")
        await post_info["source_msg"].reply_text(f"❌ Опять хрень вышла: {e}")

    finally:
        del pending_posts[post_id]


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена публикации"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("cancel_"):
        return

    source_msg_id = data.replace("cancel_", "")

    if source_msg_id in pending_posts:
        post_info = pending_posts[source_msg_id]
        await query.message.edit_text("❌ Ссыкун отменил пост. Ладно, не буду кидать.")
        stats.add_cancel()
        del pending_posts[source_msg_id]


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для админов — вброс в канал"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Ты кто такой, сука? У тебя нет прав.")
        return

    if not context.args:
        await update.message.reply_text("📝 Ну и чё кидать-то? Пиши так: /broadcast <текст>")
        return

    message = ' '.join(context.args)
    try:
        await context.bot.send_message(CHANNEL_ID, message, parse_mode=ParseMode.MARKDOWN, disable_notification=True)
        await update.message.reply_text("✅ Закинул твою мудрость в канал. Теперь все поржали.")
    except Exception as e:
        await update.message.reply_text(f"❌ Опять ты сломал, клоун: {e}")

# --- Глобальная ошибка ---


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок"""
    logger.error(msg="Ошибка у бота:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "💥 Опять всё через жопу. Я упал, но ты держись."
        )


def main():
    """Главная функция запуска бота"""
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("joke", tell_joke))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_error_handler(error_handler)

    # Обработчик вложений (фото, видео, документы и т.д.)
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (
            filters.PHOTO |
            filters.VIDEO |
            filters.AUDIO |
            filters.Document.ALL |
            filters.VOICE |
            filters.ANIMATION |
            filters.Sticker.ALL
        ),
        handle_attachment
    ))

    # Обработчик callback кнопок
    application.add_handler(CallbackQueryHandler(
        handle_cancel, pattern="^cancel_"))

    # Запускаем бота
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
