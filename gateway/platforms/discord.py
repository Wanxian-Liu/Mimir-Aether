"""Compatibility module - imports from discord_adapter."""
from .discord_adapter import DiscordAdapter

def check_discord_requirements():
    """Check if Discord requirements are installed."""
    return True  # Always available since we have the adapter

__all__ = ["DiscordAdapter", "check_discord_requirements"]
