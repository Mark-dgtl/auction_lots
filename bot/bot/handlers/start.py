"""Хендлеры команд /start и /help."""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import settings
from bot.services.backend_client import BackendClient

router = Router()
logger = logging.getLogger("bot.handlers.start")

_WELCOME = (
    "Привет! Я буду присылать уведомления о новых торгах.\n\n"
    "Чтобы получать уведомления, привяжите аккаунт:\n"
    "1. Войдите на сайт агрегатора\n"
    "2. В личном кабинете нажмите «Привязать Telegram»\n"
    "3. Перейдите по полученной ссылке\n\n"
    "Используйте /help для списка команд."
)

_HELP = (
    "Доступные команды:\n"
    "/start — приветствие и инструкция\n"
    "/start [токен] — привязать аккаунт по ссылке с сайта\n"
    "/help — список команд"
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Обрабатывает команду /start [токен].

    Если токен передан — пытается привязать Telegram-аккаунт к пользователю
    через внутренний API backend. Если токен отсутствует — показывает приветствие.

    Args:
        message: Входящее сообщение от пользователя.
    """
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) > 1:
        link_token = parts[1].strip()
        client = BackendClient(
            base_url=settings.BACKEND_INTERNAL_URL,
            token=settings.INTERNAL_API_TOKEN,
        )
        success = await client.bind_telegram(
            link_token=link_token,
            telegram_user_id=message.from_user.id,
            chat_id=message.chat.id,
        )
        if success:
            logger.info(
                "Telegram id=%d успешно привязан", message.from_user.id
            )
            await message.answer(
                "✅ Аккаунт успешно привязан! Теперь вы будете получать уведомления."
            )
        else:
            await message.answer(
                "❌ Токен неверный или истёк. Запросите новую ссылку в личном кабинете."
            )
    else:
        await message.answer(_WELCOME)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Показывает список доступных команд бота.

    Args:
        message: Входящее сообщение от пользователя.
    """
    await message.answer(_HELP)
