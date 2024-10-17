import asyncio
from telethon import TelegramClient, events

API_ID = 27318098  # Ваш реальный API ID
API_HASH = '288510762a35d32033f6e97f5efd59e1'  # Ваш реальный API Hash
BOT_TOKEN = '7561642764:AAGCXa7bchZ1KLFDr394RsP8mBmH2HphjHc'  # Ваш реальный токен бота

client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond('Привет! Я ваш бот.')

async def main():
    await client.start()
    print("Бот запущен...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
