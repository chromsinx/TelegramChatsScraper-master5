import asyncio
from telethon import TelegramClient, events, Button
from config import DESTINATION, STOP_WORDS_DESTINATION, API_ID, API_HASH, SESSION, CHATS, KEY_WORDS, STOP_WORDS
from datetime import datetime, timedelta
from rapidfuzz import fuzz
import logging
import os

# Настройка логирования с выводом в файл и консоль
LOG_FILE = 'bot.log'
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Инициализация клиента Telethon для работы с личным аккаунтом
client = TelegramClient(SESSION, API_ID, API_HASH)

# Хранилище сообщений с метками времени для фильтрации (24 часа хранения)
message_store = {}

# Период фильтрации сообщений (24 часа)
FILTER_DURATION = timedelta(days=1)

# Порог схожести сообщений для фильтрации (90%)
SIMILARITY_THRESHOLD = 90

# Параметры для логов
MARQUEE_LENGTH = 5  # количество строк, отображаемых одновременно
DELAY = 3  # задержка между обновлениями логов

# Оптимизация: создаем множество стоп-слов и ключевых слов в нижнем регистре один раз
STOP_WORDS_SET = {word.lower() for word in STOP_WORDS}
KEY_WORDS_SET = {word.lower() for word in KEY_WORDS}

def validate_config():
    """
    Проверка наличия всех обязательных конфигурационных переменных.
    Генерирует ошибку, если какая-либо переменная отсутствует или пуста.
    """
    required_globals = {
        'API_ID': API_ID,
        'API_HASH': API_HASH,
        'SESSION': SESSION,
        'DESTINATION': DESTINATION,
        'STOP_WORDS_DESTINATION': STOP_WORDS_DESTINATION,
        'CHATS': CHATS,
        'KEY_WORDS': KEY_WORDS,
        'STOP_WORDS': STOP_WORDS
    }
    for var_name, var_value in required_globals.items():
        if not var_value:
            raise ValueError(f"The required config variable '{var_name}' is not set or is empty")

def log_with_time(message):
    """ Логирование с добавлением отметки времени """
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{current_time}] {message}")

def is_similar(message_text):
    """
    Проверка схожести нового сообщения с уже существующими в хранилище.
    Если схожесть превышает порог SIMILARITY_THRESHOLD, то сообщение считается дубликатом.
    """
    for stored_message in message_store.keys():
        similarity = fuzz.ratio(stored_message, message_text)
        if similarity >= SIMILARITY_THRESHOLD:
            return True
    return False

def remove_spaces(text):
    """
    Удаляет все пробелы из строки.
    """
    return text.replace(" ", "")

def contains_stop_words(message_text):
    """
    Проверяет, содержит ли сообщение слова из стоп-листа.
    Возвращает True, если хотя бы одно слово из стоп-листа присутствует в тексте сообщения.
    Пробелы в тексте сообщения и стоп-словах игнорируются.
    """
    clean_message_text = remove_spaces(message_text.lower())
    return any(remove_spaces(stop_word) in clean_message_text for stop_word in STOP_WORDS_SET)

async def remove_old_messages():
    """
    Удаляет сообщения, которые старше FILTER_DURATION (24 часа), из хранилища.
    Это помогает поддерживать актуальность фильтрации дубликатов сообщений.
    """
    current_time = datetime.now()
    to_remove = [msg for msg, timestamp in message_store.items() if current_time - timestamp > FILTER_DURATION]
    for msg in to_remove:
        del message_store[msg]

@client.on(events.NewMessage(chats=CHATS))
async def new_message_handler(event):
    """
    Основной обработчик новых сообщений.
    Фильтрует сообщения по схожести, стоп-словам и ключевым словам.
    Пересылает сообщения в целевой чат, если они соответствуют всем условиям.
    """
    try:
        log_with_time(f'Получено новое сообщение из чата {event.chat_id}...')

        if not event.message.text:
            log_with_time("Сообщение без текста, пропускаем.")
            return

        await remove_old_messages()

        if contains_stop_words(event.message.text):
            await client.forward_messages(STOP_WORDS_DESTINATION, event.message)
            log_with_time("Сообщение содержит стоп-слова, переслано в канал для стоп-слов.")
            return

        if is_similar(event.message.text):
            log_with_time("Сообщение похоже на уже существующее (>= 90% схожести), фильтруем...")
            return

        clean_message_text = remove_spaces(event.message.text.lower())

        if any(remove_spaces(key_word) in clean_message_text for key_word in KEY_WORDS_SET):
            message_store[event.message.text] = datetime.now()
            await client.forward_messages(DESTINATION, event.message)
            log_with_time(f"Сообщение переслано: {event.message.text}")
            await asyncio.sleep(2)
        else:
            log_with_time("Сообщение не содержит ключевых слов, не пересылаем.")

    except Exception as ex:
        log_with_time(f'Ошибка при обработке сообщения: {ex}')
        await asyncio.sleep(60)

# Функция для обновления сообщения с логами
async def display_logs(event):
    """
    Отправка логов в виде бегущей строки.
    """
    with open(LOG_FILE, 'r') as log_file:
        logs = log_file.readlines()

    message = await event.respond("Логи загружаются...", buttons=[
        Button.inline("Остановить логи", b"stop_logs")
    ])

    total_lines = len(logs)
    index = 0
    try:
        while True:
            if index + MARQUEE_LENGTH > total_lines:
                index = 0  # Прокручиваем логи с начала
            current_logs = logs[index:index + MARQUEE_LENGTH]
            await message.edit("".join(current_logs))
            index += MARQUEE_LENGTH
            await asyncio.sleep(DELAY)
    except asyncio.CancelledError:
        await message.edit("Логи остановлены.")

# Обработчик команды /logs
@client.on(events.NewMessage(pattern='/logs'))
async def logs_command_handler(event):
    """
    Обработчик команды /logs, выводит логи в виде бегущей строки.
    """
    log_with_time("Пользователь запросил логи.")
    await display_logs(event)

# Обработчик нажатий на inline-кнопки
@client.on(events.CallbackQuery(data=b"stop_logs"))
async def stop_logs_handler(event):
    """
    Обработчик для остановки бегущей строки с логами.
    """
    await event.respond("Бегущая строка с логами остановлена.")

async def main():
    """
    Основная функция, запускающая клиента Telethon.
    Выполняется до тех пор, пока не будет завершено соединение.
    """
    async with client:
        log_with_time("Бот запущен...")
        await client.start()
        await client.run_until_disconnected()

if __name__ == "__main__":
    validate_config()
    asyncio.run(main())
