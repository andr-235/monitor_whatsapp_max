"""Состояния диалога для ввода ключевых слов."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class KeywordDialog(StatesGroup):
    """Состояния диалога добавления/удаления ключевых слов."""

    waiting_for_add = State()
    waiting_for_remove = State()
