"""Меню и команды Telegram-бота."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup

from bot.constants import (
    COMMAND_ADD_DESCRIPTION,
    COMMAND_HELP_DESCRIPTION,
    COMMAND_LIST_DESCRIPTION,
    COMMAND_MENU_DESCRIPTION,
    COMMAND_RECENT_DESCRIPTION,
    COMMAND_REMOVE_DESCRIPTION,
    COMMAND_SEARCH_DESCRIPTION,
    COMMAND_START_DESCRIPTION,
    MENU_BUTTON_ADD,
    MENU_BUTTON_HELP,
    MENU_BUTTON_LIST,
    MENU_BUTTON_RECENT,
    MENU_BUTTON_REMOVE,
    MENU_BUTTON_SEARCH,
    MENU_PLACEHOLDER,
)


def build_main_menu() -> ReplyKeyboardMarkup:
    """Сформировать основное меню с кнопками."""

    keyboard = [
        [KeyboardButton(text=MENU_BUTTON_RECENT), KeyboardButton(text=MENU_BUTTON_SEARCH)],
        [KeyboardButton(text=MENU_BUTTON_LIST)],
        [KeyboardButton(text=MENU_BUTTON_ADD), KeyboardButton(text=MENU_BUTTON_REMOVE)],
        [KeyboardButton(text=MENU_BUTTON_HELP)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder=MENU_PLACEHOLDER,
    )


async def setup_bot_commands(bot: Bot) -> None:
    """Настроить список команд для меню Telegram."""

    commands = [
        BotCommand(command="start", description=COMMAND_START_DESCRIPTION),
        BotCommand(command="menu", description=COMMAND_MENU_DESCRIPTION),
        BotCommand(command="help", description=COMMAND_HELP_DESCRIPTION),
        BotCommand(command="add_keyword", description=COMMAND_ADD_DESCRIPTION),
        BotCommand(command="remove_keyword", description=COMMAND_REMOVE_DESCRIPTION),
        BotCommand(command="list_keywords", description=COMMAND_LIST_DESCRIPTION),
        BotCommand(command="search", description=COMMAND_SEARCH_DESCRIPTION),
        BotCommand(command="recent", description=COMMAND_RECENT_DESCRIPTION),
    ]
    await bot.set_my_commands(commands)
