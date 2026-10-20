#!/usr/bin/env python3
"""打印增量集合的 docs 数（只读）。用于验证重放是否真写进 chroma。"""
import os
import sys
from pathlib import Path

ROOT = str(Path.home() / "src" / "MimirAether")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.chroma_session_indexer import _get_incremental_collection  # noqa: E402

coll = _get_incremental_collection()
n = coll.count()
print(f"chroma_docs={n} embed_model_env={os.getenv('MIMIR_EMBED_MODEL') or '(unset)'}")

try:
    got = coll.get(limit=1, include=["embeddings"])
    embs = got.get("embeddings")
    if embs is not None and len(embs):
        print(f"dim={len(embs[0])}")
    else:
        print("dim=(none)")
except Exception as exc:  # noqa: BLE001
    print(f"dim_probe_failed={type(exc).__name__}: {exc}")
