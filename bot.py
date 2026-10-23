import asyncio
import logging

from aiogram import Bot

from config import BOT_TOKEN, SUPPORT_CHAT_ID
from db import init_db
from handlers import dp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("support_bot")


async def main() -> None:
    init_db()
    bot = Bot(token=BOT_TOKEN)
    log.info("Бот запущен. Группа поддержки: %s", SUPPORT_CHAT_ID)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Бот остановлен.")