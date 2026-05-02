"""Compatibility module - imports from feishu_adapter."""
import os

from .feishu_adapter import FeishuAdapter


def check_feishu_requirements() -> bool:
    """Feishu needs app credentials; long connection (default) also needs lark-oapi."""
    if not (os.getenv("FEISHU_APP_ID") or "").strip():
        return False
    if not (os.getenv("FEISHU_APP_SECRET") or "").strip():
        return False
    mode = (os.getenv("FEISHU_CONNECTION_MODE") or "websocket").strip().lower()
    if mode == "websocket":
        try:
            import lark_oapi  # noqa: F401
        except ImportError:
            return False
    return True


FEISHU_AVAILABLE = True
FEISHU_DOMAIN = "open.feishu.cn"
LARK_DOMAIN = "open.larksuite.com"

__all__ = [
    "FeishuAdapter",
    "check_feishu_requirements",
    "FEISHU_AVAILABLE",
    "FEISHU_DOMAIN",
    "LARK_DOMAIN",
]
