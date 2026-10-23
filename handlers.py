import logging

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from config import SUPPORT_CHAT_ID
from db import (
    close_ticket,
    create_ticket,
    get_open_ticket_for_user,
    get_ticket_by_support_msg,
    get_ticket_status,
    set_support_msg,
)
from faq import TOPICS, faq_text

log = logging.getLogger("support_bot")

dp = Dispatcher()


def topics_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=title, callback_data=f"topic:{key}")]
        for key, title in TOPICS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def close_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Закрыть обращение", callback_data=f"close:{ticket_id}")]
        ]
    )


async def notify_closed_by_user(
    bot: Bot,
    ticket_id: int,
    user: User,
) -> None:
    close_ticket(ticket_id)
    uname = f"@{user.username}" if user.username else "нет"
    try:
        await bot.send_message(
            SUPPORT_CHAT_ID,
            f"🔒 Тикет #{ticket_id} закрыт клиентом.\n"
            f"От: {user.full_name} ({uname})\n"
            f"ID: {user.id}",
        )
    except TelegramAPIError:
        log.exception("Не удалось уведомить группу о закрытии тикета #%s клиентом", ticket_id)


async def forward_to_support(
    message: Message,
    bot: Bot,
    user: User,
    topic: str | None,
    text: str,
) -> None:
    # Без выбранной кнопки тема считается «Другое», как и у кнопки «Другое»
    topic = topic or TOPICS["other"]

    ticket_id = get_open_ticket_for_user(user.id)
    is_new = ticket_id is None
    if ticket_id is None:
        ticket_id = create_ticket(user.id, user.username, topic, text)

    uname = f"@{user.username}" if user.username else "нет"
    if is_new:
        header = f"🎫 Тикет #{ticket_id}\nТема: {topic}\n"
    else:
        header = f"💬 Тикет #{ticket_id}, новое сообщение\n"

    support_text = (
        f"{header}"
        f"От: {user.full_name} ({uname})\n"
        f"ID: {user.id}\n\n"
        f"{text}\n\n"
        "Ответьте на это сообщение, чтобы ответить пользователю."
    )
    try:
        sent = await bot.send_message(SUPPORT_CHAT_ID, support_text)
    except TelegramAPIError:
        log.exception("Не удалось отправить сообщение по тикету #%s в служебную группу", ticket_id)
        if is_new:
            # Не оставляем открытый тикет, о котором служба не знает
            close_ticket(ticket_id)
        await message.answer("Сейчас не получилось передать обращение. Попробуйте чуть позже.")
        return

    set_support_msg(ticket_id, sent.message_id)

    if is_new:
        await message.answer(
            "Обращение создано. Мы ответим как можно скорее.",
            reply_markup=close_keyboard(ticket_id),
        )
    else:
        await message.answer("Ваше сообщение добавлено в обращение.")


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Это поддержка Memory VPN.\n\n"
        "Выберите тему или опишите проблему сообщением.",
        reply_markup=topics_keyboard(),
    )


@dp.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message) -> None:
    await message.answer(faq_text())


@dp.message(Command("close"), F.chat.type == "private")
async def user_close(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None:
        return
    ticket_id = get_open_ticket_for_user(user.id)
    if ticket_id is None:
        await message.answer("У вас нет открытых обращений.")
        return
    await notify_closed_by_user(bot, ticket_id, user)
    await message.answer("Обращение закрыто. Если вопрос вернётся, напишите нам снова.")


@dp.callback_query(F.data.startswith("close:"))
async def user_close_button(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    message = callback.message
    raw_id = (callback.data or "").removeprefix("close:")
    if not raw_id.isdigit() or not isinstance(message, Message):
        return
    ticket_id = int(raw_id)
    if get_ticket_status(ticket_id) != "open":
        await message.answer("Это обращение уже закрыто.")
        return
    await notify_closed_by_user(bot, ticket_id, callback.from_user)
    await message.answer("Обращение закрыто. Если вопрос вернётся, напишите нам снова.")


@dp.callback_query(F.data.startswith("topic:"))
async def topic_chosen(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    key = (callback.data or "").removeprefix("topic:")
    title = TOPICS.get(key)
    message = callback.message
    if title is None or not isinstance(message, Message):
        return

    await forward_to_support(
        message,
        bot,
        callback.from_user,
        title,
        f"Пользователь выбрал тему: {title}",
    )


@dp.message(F.chat.type == "private", F.text)
async def user_message(message: Message, bot: Bot) -> None:
    user = message.from_user
    text = message.text
    if user is None or text is None:
        return
    await forward_to_support(message, bot, user, None, text)


@dp.message(Command("close"), F.chat.id == SUPPORT_CHAT_ID, F.reply_to_message)
async def operator_close(message: Message, bot: Bot) -> None:
    operator = message.from_user
    replied = message.reply_to_message
    if operator is None or operator.is_bot or replied is None:
        return
    row = get_ticket_by_support_msg(replied.message_id)
    if row is None:
        return
    ticket_id, user_id = row
    if get_ticket_status(ticket_id) != "open":
        await message.reply(f"Тикет #{ticket_id} уже закрыт.")
        return
    close_ticket(ticket_id)
    try:
        await bot.send_message(
            user_id,
            "✅ Обращение закрыто поддержкой. Если вопрос остался, напишите нам снова.",
        )
    except TelegramAPIError:
        log.exception("Не удалось уведомить пользователя о закрытии #%s", ticket_id)
    await message.reply(f"Тикет #{ticket_id} закрыт.")


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
    if get_ticket_status(ticket_id) != "open":
        await message.reply(f"Тикет #{ticket_id} закрыт, ответ не отправлен.")
        return

    try:
        await bot.send_message(
            user_id,
            f"💬 Ответ поддержки:\n\n{text}",
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