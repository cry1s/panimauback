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
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Хранилище для отслеживания отправленных сообщений
pending_posts: Dict[str, Dict] = {}

# Забавные ответы для команды healthcheck
HEALTH_RESPONSES = [
    "🤖 Я жив и готов к работе! Как робот-пылесос, только для сообщений.",
    "✅ Всё отлично! Сижу, жду вложений, как кот у миски.",
    "🚀 Работаю на полную катушку! Быстрее меня только свет... и моя бабушка на распродаже.",
    "💪 В полном порядке! Здоровье как у быка, мозги как у компьютера, юмор как у КВНщика.",
    "🎯 На посту! Глаз не спускаю с вложений, как орёл с добычей.",
    "⚡ Заряжен на 100%! Готов форвардить всё, что движется (и имеет вложения).",
    "🎪 Работаю! Жонглирую сообщениями как цирковой артист.",
    "🔥 Горячий и готовый! Как пицца, только полезнее.",
    "🎨 В креативном настроении! Форваржу с душой и огоньком.",
    "🌟 Сияю и работаю! Как новогодняя гирлянда, только круглый год."
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
    """Получить случайную шутку с API (резервный вариант - встроенные шутки)"""
    jokes_fallback = [
        "Программист заходит в бар и заказывает 1.0 пива, потом 0 пива, потом 999999 пива, потом -1 пива, потом qwerty пива.",
        "- Сколько программистов нужно, чтобы поменять лампочку?\n- Ни одного, это аппаратная проблема.",
        "Есть только 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
        "- Почему программисты путают Хэллоуин и Рождество?\n- Потому что Oct 31 = Dec 25",
        "Жена программиста отправила его в магазин: 'Купи батон хлеба, если будут яйца - возьми десяток'. Он купил десять батонов."
    ]
    
    try:
        # Попытка получить шутку с API
        async with aiohttp.ClientSession() as session:
            # Можно использовать русскоязычное API шуток, если найдёте
            # Пока используем fallback
            return f"💭 {random.choice(jokes_fallback)}"
    except:
        return f"💭 {random.choice(jokes_fallback)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_text = """
🤖 *Привет! Я бот-форвардер с характером!*

Моя основная работа - пересылать вложения из группы в канал.
Но я также умею:

📌 *Основные функции:*
• Автоматически пересылаю все вложения в канал
• Даю 5 секунд на отмену публикации
• Веду статистику работы

🎮 *Команды:*
• /health - проверить моё самочувствие
• /stats - посмотреть статистику
• /joke - рассказать анекдот
• /help - показать эту справку

_Создан с любовью и щепоткой юмора_ ❤️
    """
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда проверки здоровья бота"""
    response = random.choice(HEALTH_RESPONSES)
    uptime = stats.get_uptime()
    
    # Добавляем случайную шутку иногда
    if random.random() < 0.3:  # 30% шанс
        joke = await get_joke()
        response += f"\n\n{joke}"
    
    response += f"\n\n⏱ Работаю уже: {uptime}"
    response += f"\n📊 Переслано файлов: {stats.total_forwarded}"
    
    await update.message.reply_text(response)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику работы бота"""
    if not stats.total_forwarded:
        await update.message.reply_text("📊 Пока что статистика пуста. Жду первые вложения!")
        return
    
    text = f"""📊 *Статистика работы:*
    
⏱ Время работы: {stats.get_uptime()}
📤 Всего переслано: {stats.total_forwarded}
❌ Отменено: {stats.cancelled}
✅ Успешно опубликовано: {stats.total_forwarded - stats.cancelled}

📁 *По типам файлов:*"""
    
    for file_type, count in stats.by_type.items():
        emoji = FILE_EMOJIS.get(file_type, '📎')
        text += f"\n{emoji} {file_type}: {count}"
    
    if stats.cancelled > 0:
        cancel_rate = (stats.cancelled / stats.total_forwarded) * 100
        text += f"\n\n🎯 Процент отмен: {cancel_rate:.1f}%"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def tell_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассказать анекдот"""
    joke = await get_joke()
    await update.message.reply_text(joke)

async def handle_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с вложениями из группы"""
    
    # Проверяем, что сообщение из нужной группы
    if update.message.chat_id != GROUP_ID:
        print(update.message.chat_id, GROUP_ID)
        return
    
    message = update.message
    file_type = None
    file_id = None
    caption = message.caption or ""
    
    # Определяем тип вложения
    if message.photo:
        file_type = 'photo'
        file_id = message.photo[-1].file_id  # Берём самое большое качество
    elif message.video:
        file_type = 'video'
        file_id = message.video.file_id
    elif message.audio:
        file_type = 'audio'
        file_id = message.audio.file_id
    elif message.voice:
        file_type = 'voice'
        file_id = message.voice.file_id
    elif message.document:
        file_type = 'document'
        file_id = message.document.file_id
    elif message.animation:
        file_type = 'animation'
        file_id = message.animation.file_id
    elif message.sticker:
        file_type = 'sticker'
        file_id = message.sticker.file_id
    
    if not file_type:
        return
    
    try:
        # Пересылаем в канал
        if file_type == 'photo':
            channel_msg = await context.bot.send_photo(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'video':
            channel_msg = await context.bot.send_video(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'audio':
            channel_msg = await context.bot.send_audio(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'voice':
            channel_msg = await context.bot.send_voice(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'document':
            channel_msg = await context.bot.send_document(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'animation':
            channel_msg = await context.bot.send_animation(
                CHANNEL_ID, 
                file_id, 
            )
        elif file_type == 'sticker':
            channel_msg = await context.bot.send_sticker(CHANNEL_ID, file_id)
            # Для стикеров отправляем подпись отдельным сообщением
        
        # Создаём кнопку отмены
        keyboard = [[InlineKeyboardButton("❌ Не публиковать", callback_data=f"cancel_{channel_msg.message_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение с кнопкой отмены
        cancel_msg = await message.reply_text(
            f"✅ Опубликовано в канале!\nЕсть 5 секунд чтобы отменить.",
            reply_markup=reply_markup
        )
        
        # Сохраняем информацию для возможной отмены
        pending_posts[str(channel_msg.message_id)] = {
            'channel_msg_id': channel_msg.message_id,
            'cancel_msg': cancel_msg,
            'file_type': file_type,
            'timestamp': datetime.now()
        }
        
        # Добавляем в статистику
        stats.add_forward(file_type)
        
        # Планируем удаление кнопки через 5 секунд
        context.job_queue.run_once(
            delete_cancel_button,
            5,
            data={'post_id': str(channel_msg.message_id), 'chat_id': message.chat_id}
        )
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await message.reply_text(f"❌ Ошибка при публикации: {str(e)}")

async def delete_cancel_button(context: ContextTypes.DEFAULT_TYPE):
    """Удаление кнопки отмены после таймаута"""
    post_id = context.job.data['post_id']
    
    if post_id in pending_posts:
        post_info = pending_posts[post_id]
        try:
            # Редактируем сообщение, убирая кнопку
            await post_info['cancel_msg'].edit_text(
                "✅ Опубликовано в канале!",
                reply_markup=None
            )
            # Удаляем сообщение через 2 секунды
            await asyncio.sleep(2)
            await post_info['cancel_msg'].delete()
        except:
            pass
        finally:
            del pending_posts[post_id]

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки отмены"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID сообщения в канале из callback_data
    data = query.data
    if not data.startswith("cancel_"):
        return
    
    channel_msg_id = data.replace("cancel_", "")
    
    if channel_msg_id in pending_posts:
        post_info = pending_posts[channel_msg_id]
        
        try:
            # Удаляем сообщение из канала
            await context.bot.delete_message(CHANNEL_ID, post_info['channel_msg_id'])
            
            # Обновляем сообщение в группе
            await query.message.edit_text(
                "❌ Публикация отменена!",
                reply_markup=None
            )
            
            # Добавляем в статистику отмену
            stats.add_cancel()
            
            # Удаляем из pending
            del pending_posts[channel_msg_id]
            
            # Удаляем сообщение через 3 секунды
            await asyncio.sleep(3)
            await query.message.delete()
            
        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}")
            await query.message.edit_text(
                "❌ Не удалось отменить публикацию.",
                reply_markup=None
            )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для админов - отправка сообщения в канал"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 У вас нет прав для этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: /broadcast <сообщение>")
        return
    
    message = ' '.join(context.args)
    try:
        await context.bot.send_message(CHANNEL_ID, message, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ Сообщение отправлено в канал!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

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
    application.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel_"))
    
    # Запускаем бота
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
