"""
JSON repair utilities for tool call arguments.

When LLMs generate tool call arguments, they sometimes produce
malformed JSON. This module attempts to repair common errors
before giving up.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


def repair_json_arguments(raw: str) -> str:
    """
    Attempt to repair common JSON errors in tool call arguments.

    Returns the repaired JSON string, or the original if no repair is needed.
    Raises ValueError if repair fails.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Arguments must be a non-empty string")

    raw = raw.strip()

    # Try parsing directly first
    try:
        json.loads(raw)
        return raw  # It's valid, no repair needed
    except json.JSONDecodeError:
        pass

    repaired = raw

    # Common LLM JSON errors and their fixes:

    # 1. Trailing commas before closing brace/bracket
    #    {"key": "value",} -> {"key": "value"}
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)

    # 2. Single quotes instead of double quotes
    #    {'key': 'value'} -> {"key": "value"}
    #    Only apply if no double quotes are present (to avoid breaking
    #    strings that legitimately contain single quotes)
    if '"' not in repaired:
        repaired = repaired.replace("'", '"')

    # 3. Missing quotes around keys
    #    {key: "value"} -> {"key": "value"}
    repaired = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', repaired)

    # 4. Unescaped newlines inside string values
    #    LLMs sometimes put literal newlines in JSON strings
    #    {"content": "line1\nline2"} -> keep the \n (it's valid JSON)
    #    But {"content": "line1
    #    line2"} -> need to escape
    if '\n' in repaired:
        # Find unescaped newlines inside strings and escape them
        in_string = False
        escaped = False
        result = []
        for ch in repaired:
            if escaped:
                escaped = False
                result.append(ch)
                continue
            if ch == '\\':
                escaped = True
                result.append(ch)
                continue
            if ch == '"' and not escaped:
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ch == '\n':
                result.append('\\n')
                continue
            if in_string and ch == '\r':
                result.append('\\r')
                continue
            if in_string and ch == '\t':
                result.append('\\t')
                continue
            result.append(ch)
        repaired = ''.join(result)

    # 5. Concatenated strings without comma
    #    {"a": "b""c": "d"} -> {"a": "b", "c": "d"}
    repaired = re.sub(r'"\s*"', '", "', repaired)

    # 6. Remove BOM and zero-width characters
    repaired = repaired.replace('\ufeff', '').replace('\u200b', '')

    # Try parsing again after all repairs
    try:
        json.loads(repaired)
        logger.info("Successfully repaired malformed JSON arguments")
        return repaired
    except json.JSONDecodeError:
        pass

    # If still invalid, raise so caller can use original error
    raise ValueError(f"Unable to repair JSON: {raw[:200]}")
