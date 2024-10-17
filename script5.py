import asyncio
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError  # Добавлено для обработки ошибки лимита
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

# Параметры для логов (по умолчанию)
MARQUEE_LENGTH = 5  # количество строк, отображаемых одновременно
DELAY = 3  # задержка между обновлениями логов

# Оптимизация: создаем множество стоп-слов и ключевых слов в нижнем регистре один раз
STOP_WORDS_SET = {word.lower() for word in STOP_WORDS}
KEY_WORDS_SET = {word.lower() for word in KEY_WORDS}

# Флаг для остановки отображения логов
log_display_active = False

def validate_config():
    """ Проверка наличия всех обязательных конфигурационных переменных. """
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
    """ Проверка схожести нового сообщения с уже существующими в хранилище. """
    for stored_message in message_store.keys():
        similarity = fuzz.ratio(stored_message, message_text)
        if similarity >= SIMILARITY_THRESHOLD:
            return True
    return False

def remove_spaces(text):
    """ Удаляет все пробелы из строки. """
    return text.replace(" ", "")

def contains_stop_words(message_text):
    """ Проверяет, содержит ли сообщение слова из стоп-листа. """
    clean_message_text = remove_spaces(message_text.lower())
    return any(remove_spaces(stop_word) in clean_message_text for stop_word in STOP_WORDS_SET)

async def remove_old_messages():
    """ Удаляет старые сообщения (старше FILTER_DURATION) из хранилища. """
    current_time = datetime.now()
    to_remove = [msg for msg, timestamp in message_store.items() if current_time - timestamp > FILTER_DURATION]
    for msg in to_remove:
        del message_store[msg]

async def display_logs(event):
    """ Отправка логов в виде бегущей строки. """
    global log_display_active
    global message  # Укажите, что message глобальная    
    log_display_active = True
    message = None  # Инициализируем переменную здесь
    try:
        with open(LOG_FILE, 'r') as log_file:
            logs = log_file.readlines()

        message = await event.respond("Логи загружаются...", buttons=[
            Button.inline("Остановить логи", b"stop_logs")
        ])

        total_lines = len(logs)
        index = 0
        while log_display_active:
            if index + MARQUEE_LENGTH > total_lines:
                index = 0  # Прокручиваем логи с начала
            current_logs = logs[index:index + MARQUEE_LENGTH]  # Исправлено: название переменной
            try:
                await message.edit("".join(current_logs))
            except FloodWaitError as e:
                log_with_time(f'Превышение лимита: нужно подождать {e.seconds} секунд.')
                await asyncio.sleep(e.seconds)  # Ждем перед попыткой снова
                continue  # Продолжаем с того же индекса
            index += MARQUEE_LENGTH
            await asyncio.sleep(DELAY)
    except Exception as e:
        log_with_time(f'Ошибка при показе логов: {e}')
    finally:
        if message:
            await message.edit("Бегущая строка логов остановлена.")

async def periodic_update_logs():
    """ Периодическое обновление логов для проверки работы бота. """
    while True:
        try:
            # Здесь можно добавить логику обновления логов или другую проверочную работу
            log_with_time("Обновление логов...")
        except Exception as e:
            log_with_time(f'Ошибка при обновлении логов: {e}')
        await asyncio.sleep(DELAY)

# Обработчик команды /logs
@client.on(events.NewMessage(pattern='/logs'))
async def logs_command_handler(event):
    """ Обработчик команды /logs, выводит логи в виде бегущей строки. """
    log_with_time("Пользователь запросил логи.")
    await display_logs(event)

# Обработчик команды /start
@client.on(events.NewMessage(pattern='/start'))
async def start_command_handler(event):
    """ Обработчик команды /start, выводит приветственное сообщение с inline-кнопками. """
    log_with_time("Пользователь запустил бота.")
    await event.respond(
        "Привет! Я бот для работы с логами.\nВыберите одну из функций ниже:",
        buttons=[
            [Button.inline("Показать логи", b"show_logs"), Button.inline("Остановить логи", b"stop_logs")],
            [Button.inline("Показать последние 10 сообщений", b"latest_logs")],
            [Button.inline("Настроить задержку", b"set_delay"), Button.inline("Настроить количество строк", b"set_marquee")]
        ]
    )

# Обработчик команды /help
@client.on(events.NewMessage(pattern='/help'))
async def help_command_handler(event):
    """ Обработчик команды /help, выводит список доступных команд. """
    await event.respond(
        "/start — Запустить бота\n"
        "/help — Показать команды\n"
        "/logs — Показать логи\n"
        "/stop — Остановить показ логов\n"
        "/latest — Показать последние 10 строк логов\n"
        "/setdelay <секунды> — Настроить задержку между обновлениями\n"
        "/setmarquee <количество> — Настроить количество строк для показа"
    )

# Обработчик команды /stop
@client.on(events.NewMessage(pattern='/stop'))
async def stop_command_handler(event):
    """ Обработчик команды /stop, останавливает процесс показа логов. """
    global log_display_active
    log_display_active = False
    log_with_time("Пользователь остановил показ логов.")
    await event.respond("Показ логов остановлен.")

# Обработчик команды /latest
@client.on(events.NewMessage(pattern='/latest'))
async def latest_command_handler(event):
    """ Обработчик команды /latest, выводит последние 10 строк логов. """
    try:
        with open(LOG_FILE, 'r') as log_file:
            logs = log_file.readlines()[-10:]
        await event.respond("Последние 10 строк логов:\n" + "".join(logs))
    except Exception as e:
        log_with_time(f'Ошибка при показе последних логов: {e}')
        await event.respond("Не удалось загрузить последние строки логов.")

# Обработчик команды /setdelay
@client.on(events.NewMessage(pattern='/setdelay (\d+)'))
async def setdelay_command_handler(event):
    """ Обработчик команды /setdelay, изменяет задержку между обновлениями логов. """
    global DELAY
    new_delay = int(event.pattern_match.group(1))
    DELAY = new_delay
    log_with_time(f"Пользователь изменил задержку на {new_delay} секунд.")
    await event.respond(f"Задержка обновления логов изменена на {new_delay} секунд.")

# Обработчик команды /setmarquee
@client.on(events.NewMessage(pattern='/setmarquee (\d+)'))
async def setmarquee_command_handler(event):
    """ Обработчик команды /setmarquee, изменяет количество строк, отображаемых одновременно. """
    global MARQUEE_LENGTH
    new_length = int(event.pattern_match.group(1))
    MARQUEE_LENGTH = new_length
    log_with_time(f"Пользователь изменил количество строк на {new_length}.")
    await event.respond(f"Количество строк для отображения изменено на {new_length}.")

# Обработчики нажатий на inline-кнопки
@client.on(events.CallbackQuery(data=b"stop_logs"))
async def stop_logs_handler(event):
    """ Обработчик для остановки показа логов по нажатию inline-кнопки. """
    global log_display_active
    log_display_active = False
    log_with_time("Пользователь остановил показ логов через кнопку.")
    await event.edit("Показ логов остановлен.")

@client.on(events.CallbackQuery(data=b"show_logs"))
async def show_logs_handler(event):
    """ Обработчик для показа логов по нажатию inline-кнопки. """
    log_with_time("Пользователь начал показ логов через кнопку.")
    await display_logs(event)

@client.on(events.CallbackQuery(data=b"latest_logs"))
async def latest_logs_handler(event):
    """ Обработчик для показа последних 10 строк логов по нажатию inline-кнопки. """
    await latest_command_handler(event)

# Главная функция для запуска бота
async def main():
    validate_config()
    await client.start()
    asyncio.create_task(periodic_update_logs())  # Запуск функции обновления логов
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
