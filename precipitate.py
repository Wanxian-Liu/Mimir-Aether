#!/usr/bin/env python3
"""
precipitate.py — 从对话上下文中提取结晶（关键洞察），保存到 ~/.mimiraether/precipitates/

用法:
    echo "对话上下文..." | python precipitate.py
    python precipitate.py <文件路径>
    python precipitate.py "原始文本上下文..."
"""

import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path

PRECIPITATES_DIR = Path.home() / ".mimiraether" / "precipitates"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """\
You are a knowledge crystallization engine. Extract key insights from the context.

Extract only what is genuinely worth preserving:
1. **Decisions** — What was decided and why
2. **Lessons** — What worked, what failed, surprises
3. **Patterns** — Conventions, constraints, recurring themes
4. **Open Questions** — Unresolved items

Be concise. Skip greetings, trivialities, operational noise.
If nothing is worth preserving, say so in one line."""


def ensure_dir() -> None:
    PRECIPITATES_DIR.mkdir(parents=True, exist_ok=True)


def read_context() -> str:
    """Read context from file arg, raw text arg, or stdin."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        path = Path(arg)
        if path.exists():
            return path.read_text()
        return arg  # raw text

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("Usage: echo '<context>' | python precipitate.py", file=sys.stderr)
    print("   or: python precipitate.py <file_or_text>", file=sys.stderr)
    sys.exit(1)


def call_deepseek(context: str) -> str:
    """Call DeepSeek-V3 to extract crystallized insights."""
    if not DEEPSEEK_API_KEY:
        print("Error: DEEPSEEK_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    import urllib.request
    import urllib.error

    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract insights from:\n\n{context}"}
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"API Error ({e.code}): {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Request Error: {e}", file=sys.stderr)
        sys.exit(1)


def save(content: str) -> Path:
    """Save precipitate as Markdown file."""
    ensure_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = str(uuid.uuid4())[:8]
    path = PRECIPITATES_DIR / f"{stamp}_{short_id}.md"
    path.write_text(f"# Precipitate {stamp}\n\n{content}")
    return path


def main() -> None:
    context = read_context()
    if len(context) < 50:
        print("Error: context too short (< 50 chars)", file=sys.stderr)
        sys.exit(1)

    print(f"[precipitate] {len(context)} chars → DeepSeek-V3 ...", file=sys.stderr)
    result = call_deepseek(context)
    filepath = save(result)

    print(f"[precipitate] saved → {filepath}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()