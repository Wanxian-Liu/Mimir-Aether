"""Ops-editable redaction rules (HERM-RED-02).

Loads ``redact_rules.json`` from ``$MIMIR_AETHER_HOME/data/`` (or ``MIMIR_REDACT_RULES``)
with fallback to the repo template ``data/redact_rules.json``. Applied after built-in
patterns in :func:`agent.redact.redact_sensitive_text`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Pattern

logger = logging.getLogger(__name__)

_REPO_DATA_RULES = Path(__file__).resolve().parents[1] / "data" / "redact_rules.json"

_rules_cache: Optional["RedactRulesConfig"] = None
_cache_path: Optional[Path] = None


@dataclass
class RedactRulesConfig:
    regex_patterns: List[Pattern[str]] = field(default_factory=list)
    query_param_res: List[Pattern[str]] = field(default_factory=list)
    json_field_res: List[Pattern[str]] = field(default_factory=list)


def reset_redact_rules_cache() -> None:
    global _rules_cache, _cache_path
    _rules_cache = None
    _cache_path = None


def resolve_redact_rules_path() -> Optional[Path]:
    """Return the rules file path if one should be loaded."""
    override = os.getenv("MIMIR_REDACT_RULES", "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from mimir_constants import get_mimir_data_dir

        home_rules = get_mimir_data_dir() / "redact_rules.json"
        if home_rules.is_file():
            return home_rules
    except Exception:
        pass
    if _REPO_DATA_RULES.is_file():
        return _REPO_DATA_RULES
    return None


def _compile_regex(entry: dict) -> Optional[Pattern[str]]:
    raw = (entry.get("pattern") or "").strip()
    if not raw:
        return None
    flags = 0
    flag_str = (entry.get("flags") or "").lower()
    if "i" in flag_str:
        flags |= re.IGNORECASE
    if "m" in flag_str:
        flags |= re.MULTILINE
    if "s" in flag_str:
        flags |= re.DOTALL
    try:
        return re.compile(raw, flags)
    except re.error as exc:
        rid = entry.get("id") or raw[:40]
        logger.warning("redact_rules: skip invalid regex %r: %s", rid, exc)
        return None


def _compile_query_param_names(names: Iterable[str]) -> List[Pattern[str]]:
    compiled: List[Pattern[str]] = []
    for name in names:
        n = (name or "").strip()
        if not n:
            continue
        compiled.append(
            re.compile(
                rf"([?&]{re.escape(n)}=)([^&\s#\"']+)",
                re.IGNORECASE,
            )
        )
    return compiled


def _compile_json_field_names(names: Iterable[str]) -> List[Pattern[str]]:
    compiled: List[Pattern[str]] = []
    for name in names:
        n = (name or "").strip()
        if not n:
            continue
        compiled.append(
            re.compile(
                rf'("{re.escape(n)}")\s*:\s*"([^"]+)"',
                re.IGNORECASE,
            )
        )
    return compiled


def _parse_rules_payload(data: Any) -> RedactRulesConfig:
    if not isinstance(data, dict):
        return RedactRulesConfig()
    regex_patterns: List[Pattern[str]] = []
    for entry in data.get("regex_patterns") or []:
        if not isinstance(entry, dict):
            continue
        pat = _compile_regex(entry)
        if pat is not None:
            regex_patterns.append(pat)
    query_names = data.get("query_param_names") or []
    json_names = data.get("json_field_names") or []
    if not isinstance(query_names, list):
        query_names = []
    if not isinstance(json_names, list):
        json_names = []
    return RedactRulesConfig(
        regex_patterns=regex_patterns,
        query_param_res=_compile_query_param_names(query_names),
        json_field_res=_compile_json_field_names(json_names),
    )


def _read_rules_file(path: Path) -> RedactRulesConfig:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("redact_rules: cannot read %s: %s", path, exc)
        return RedactRulesConfig()
    if not raw.strip():
        return RedactRulesConfig()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("redact_rules: invalid JSON in %s: %s", path, exc)
        return RedactRulesConfig()
    return _parse_rules_payload(data)


def load_redact_rules(path: Optional[Path] = None) -> RedactRulesConfig:
    """Load rules from *path*, env/home/repo resolution, or return cached config."""
    global _rules_cache, _cache_path
    resolved = path if path is not None else resolve_redact_rules_path()
    if path is None and _rules_cache is not None and resolved == _cache_path:
        return _rules_cache
    if resolved is None or not resolved.is_file():
        cfg = RedactRulesConfig()
    else:
        cfg = _read_rules_file(resolved)
    if path is None:
        _rules_cache = cfg
        _cache_path = resolved
    return cfg


def _mask_value(value: str) -> str:
    from agent.redact import _mask_token

    return _mask_token(value)


def apply_configurable_redaction(text: str, rules: RedactRulesConfig) -> str:
    if not text or not rules:
        return text
    for pat in rules.regex_patterns:
        text = pat.sub(lambda m: _mask_value(m.group(0)), text)
    for pat in rules.query_param_res:
        text = pat.sub(lambda m: f"{m.group(1)}{_mask_value(m.group(2))}", text)
    for pat in rules.json_field_res:
        text = pat.sub(
            lambda m: f'{m.group(1)}: "{_mask_value(m.group(2))}"',
            text,
        )
    return text


def apply_loaded_rules(text: str) -> str:
    """Apply ops rules after built-in redaction (no-op when disabled upstream)."""
    return apply_configurable_redaction(text, load_redact_rules())
