"""受控实验：resolve_embedding_function 是否复用已加载模型。

背景（2026-10-21 实测）：单条查询 COLD 17.63s / WARM 13.92s，两次都打印
"Loading weights" ⇒ 每次调用都重新从盘加载 bge-m3（~2.2GB RSS）。
真正的语义延迟 ≈13.9s，而 semantic_timeout_s=5.0 ⇒ 生产每条查询必降级。

判据（两向）：
  1. 同一模型路径连续两次 resolve 必须返回**同一实例**（identity）⇒ 不重载
  2. 不同模型路径必须返回**不同实例**（负控：缓存不能串味）
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_MODEL = os.path.expanduser("~/models/bge-m3")

pytestmark = pytest.mark.skipif(
    not Path(_MODEL).is_dir(),
    reason="需要本地 bge-m3 模型",
)


def test_same_model_path_reuses_instance():
    from tools.chroma_session_indexer import resolve_embedding_function

    os.environ["MIMIR_EMBED_MODEL"] = _MODEL
    ef1 = resolve_embedding_function()
    ef2 = resolve_embedding_function()
    assert ef1 is ef2, (
        "两次 resolve 返回了不同实例 ⇒ 每次都重新加载模型 "
        "(实测每条查询多付 ~14s 与 ~2.2GB RSS)"
    )


def test_different_model_path_does_not_share_instance():
    """负控：缓存必须以 model_path 为键，不能把 A 的实例给 B。"""
    from tools.chroma_session_indexer import resolve_embedding_function

    os.environ["MIMIR_EMBED_MODEL"] = _MODEL
    ef_a = resolve_embedding_function()

    os.environ["MIMIR_EMBED_MODEL"] = os.path.expanduser("~/models/__definitely_not_here__")
    try:
        ef_b = resolve_embedding_function()
    except Exception:
        os.environ["MIMIR_EMBED_MODEL"] = _MODEL
        return  # 抛错 = 未复用，符合预期
    os.environ["MIMIR_EMBED_MODEL"] = _MODEL
    assert ef_b is not ef_a, "不同 model_path 复用了同一实例 ⇒ 缓存键错误"


def test_hash_fallback_also_reused():
    """未配置模型时的默认后端也应复用（hash EF 也不该每轮重建）。"""
    from tools.chroma_session_indexer import resolve_embedding_function

    os.environ.pop("MIMIR_EMBED_MODEL", None)
    a = resolve_embedding_function()
    b = resolve_embedding_function()
    os.environ["MIMIR_EMBED_MODEL"] = _MODEL
    assert a is b, "未配置模型时的默认后端每轮重建"
