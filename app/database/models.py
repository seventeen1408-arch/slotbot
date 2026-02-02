"""Модели данных."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Модель пользователя."""
    user_id: int
    username: Optional[str] = None
    language: str = "ru"
    is_subscribed: bool = False
    signals_unlocked: bool = False
    casino_clicked: bool = False
    casino_click_time: Optional[int] = None
    unlock_after: Optional[int] = None
    funnel_stage: int = 0
    last_active: Optional[int] = None
    casino_clicks_count: int = 0
    subscription_checked_at: Optional[int] = None
    casino_id: Optional[str] = None
    is_deposited: bool = False
    created_at: Optional[int] = None


@dataclass
class Event:
    """Модель события."""
    id: int
    user_id: int
    event_type: str
    details: Optional[str] = None
    created_at: Optional[int] = None
