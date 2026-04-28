"""Compatibility module - imports from telegram_adapter."""
from .telegram_adapter import TelegramAdapter

def check_telegram_requirements():
    """Check if Telegram requirements are installed."""
    return True  # Always available since we have the adapter

__all__ = ["TelegramAdapter", "check_telegram_requirements"]
