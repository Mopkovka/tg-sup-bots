import asyncio
import logging
import os
import sqlite3
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("support_bot")

DB_PATH = "tickets.db"


def load_config() -> tuple[str, int]:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    raw_chat_id = (os.getenv("SUPPORT_CHAT_ID") or "").strip()

    if not token:
        raise SystemExit("В файле .env не задан BOT_TOKEN.")
    try:
        chat_id = int(raw_chat_id)
    except ValueError:
        raise SystemExit("SUPPORT_CHAT_ID должен быть числом, например -1003888015937.")
    return token, chat_id


BOT_TOKEN, SUPPORT_CHAT_ID = load_config()


# ---------- База тикетов ----------

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                support_msg_id INTEGER
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_support_msg "
            "ON tickets (support_msg_id)"
        )


def create_ticket(user_id: int, username: str | None, text: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, text, datetime.now(UTC).isoformat()),
        )
        return int(cur.lastrowid or 0)


def set_support_msg(ticket_id: int, msg_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tickets SET support_msg_id = ? WHERE id = ?",
            (msg_id, ticket_id),
        )


def get_ticket_by_support_msg(msg_id: int) -> tuple[int, int] | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, user_id FROM tickets WHERE support_msg_id = ?",
            (msg_id,),
        ).fetchone()
    if row is None:
        return None
    return int(row[0]), int(row[1])


# ---------- Бот ----------

dp = Dispatcher()


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Это поддержка Memory VPN.\n\n"
        "Опишите вашу проблему одним сообщением: подключение, настройка, оплата или подписка. "
        "Мы создадим обращение и ответим здесь."
    )


@dp.message(F.chat.type == "private", F.text)
async def user_message(message: Message, bot: Bot) -> None:
    user = message.from_user
    text = message.text
    if user is None or text is None:
        return

    ticket_id = create_ticket(user.id, user.username, text)

    username = f"@{user.username}" if user.username else "нет"
    support_text = (
        f"🎫 Тикет #{ticket_id}\n"
        f"От: {user.full_name} ({username})\n"
        f"ID: {user.id}\n\n"
        f"{text}\n\n"
        "Ответьте на это сообщение, чтобы ответить пользователю."
    )

    try:
        sent = await bot.send_message(SUPPORT_CHAT_ID, support_text)
    except TelegramAPIError:
        log.exception("Не удалось отправить тикет #%s в служебную группу", ticket_id)
        await message.answer("Сейчас не получилось передать обращение. Попробуйте чуть позже.")
        return

    set_support_msg(ticket_id, sent.message_id)
    await message.answer(f"Обращение #{ticket_id} создано. Мы ответим как можно скорее.")


@dp.message(F.chat.id == SUPPORT_CHAT_ID, F.reply_to_message, F.text)
async def operator_reply(message: Message, bot: Bot) -> None:
    operator = message.from_user
    if operator is None or operator.is_bot:
        return

    replied = message.reply_to_message
    text = message.text
    if replied is None or text is None:
        return

    row = get_ticket_by_support_msg(replied.message_id)
    if row is None:
        return

    ticket_id, user_id = row

    try:
        await bot.send_message(
            user_id,
            f"💬 Ответ поддержки по обращению #{ticket_id}:\n\n{text}",
        )
    except TelegramForbiddenError:
        await message.reply(
            f"Не удалось отправить ответ по тикету #{ticket_id}: "
            "пользователь заблокировал бота."
        )
        return
    except TelegramAPIError:
        log.exception("Ошибка отправки ответа по тикету #%s", ticket_id)
        await message.reply(f"Ошибка отправки ответа по тикету #{ticket_id}. Попробуйте ещё раз.")
        return

    await message.reply(f"Ответ отправлен пользователю (тикет #{ticket_id}).")


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