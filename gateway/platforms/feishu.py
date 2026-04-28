"""Compatibility module - imports from feishu_adapter."""
from .feishu_adapter import FeishuAdapter

def check_feishu_requirements():
    """Check if Feishu requirements are installed."""
    return True  # Always available since we have the adapter

FEISHU_AVAILABLE = True
FEISHU_DOMAIN = "open.feishu.cn"
LARK_DOMAIN = "open.larksuite.com"

__all__ = ["FeishuAdapter", "check_feishu_requirements", "FEISHU_AVAILABLE", "FEISHU_DOMAIN", "LARK_DOMAIN"]
