"""回归闸：torch 线程数默认值不得回到 16（2026-10-21 实测 53.8x 劣化）。

角色卡（Performance Benchmarker）「Validate performance improvements with
before/after comparisons」。本文件把那次对比固化成闸，防止默认值被改回去。
"""
from __future__ import annotations


def test_default_num_threads_is_within_budget():
    """16 线程在 16 核机器上是超订：单条 encode 10.20s vs 4 线程 0.19s。"""
    from tools.chroma_session_indexer import LocalSentenceTransformerEmbeddingFunction as EF

    assert EF.DEFAULT_NUM_THREADS <= 4, (
        f"DEFAULT_NUM_THREADS={EF.DEFAULT_NUM_THREADS} 超预算；"
        "实测 16 线程单条 encode 10.20s、4 线程 0.19s（53.8x），"
        "而 semantic_timeout_s=5.0 ⇒ 会让每条语义查询降级为关键字"
    )


def test_thread_env_override_is_honored(monkeypatch):
    """保留 env 覆写口子：批式回填若确需更多线程，须能显式调且不被默认值压住。"""
    import inspect

    from tools import chroma_session_indexer as csi

    src = inspect.getsource(csi.LocalSentenceTransformerEmbeddingFunction.__init__)
    assert "MIMIR_EMBED_NUM_THREADS" in src, "env 覆写口子被移除"
