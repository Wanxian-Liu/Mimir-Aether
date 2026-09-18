"""
Resolve default LLM id for CLI/API.

Priority: DEFAULT_MODEL → MIMIR_MODEL → LLM_MODEL → llm_config.yaml `llm.model`.
`get_available_models()` returns (model_id, display_name, note) tuples for `cli model`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import yaml

_CONFIG_PATH = Path(__file__).parent / "llm_config.yaml"


def _load_yaml_model() -> str:
    if not _CONFIG_PATH.exists():
        return "deepseek-chat"
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    llm = data.get("llm") or {}
    return str(llm.get("model") or "deepseek-chat").strip() or "deepseek-chat"


_yaml_default = _load_yaml_model()
DEFAULT_MODEL = _yaml_default


def get_model() -> str:
    for key in ("DEFAULT_MODEL", "MIMIR_MODEL", "LLM_MODEL"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return _yaml_default


def get_available_models() -> List[Tuple[str, str, str]]:
    """Curated ids validated by `cli.py models --set`; extend as providers are added."""
    return [
        ("deepseek-chat", "DeepSeek Chat", "DeepSeek 对话"),
        ("deepseek-reasoner", "DeepSeek Reasoner", "DeepSeek 推理"),
        ("kimi-k2-0711-preview", "Kimi K2", "Moonshot Kimi"),
        ("moonshot-v1-8k", "Moonshot v1 8k", "Moonshot"),
        ("gpt-4o", "GPT-4o", "OpenAI 兼容端点"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4", "Anthropic"),
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "Anthropic"),
    ]
