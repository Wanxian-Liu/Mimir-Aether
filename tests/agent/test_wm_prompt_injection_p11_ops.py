"""WM-P11-OPS: pending VoE learning context reaches system prompt once."""

from __future__ import annotations

from agent.wm_voe_learning import (
    pop_wm_learning_context_block_for_prompt,
    reset_pending_wm_learning_context_for_test,
    set_pending_wm_learning_context,
)


def test_pop_wm_block_once(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_REPLAN_CTX", "1")
    reset_pending_wm_learning_context_for_test()
    set_pending_wm_learning_context("Prior VoE: expected 'a' but got 'b'.")
    first = pop_wm_learning_context_block_for_prompt()
    second = pop_wm_learning_context_block_for_prompt()
    assert "<wm-voe-learning>" in first
    assert "Prior VoE" in first
    assert second == ""


def test_pop_wm_block_disabled_when_env_off(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_REPLAN_CTX", "0")
    reset_pending_wm_learning_context_for_test()
    set_pending_wm_learning_context("should not appear")
    assert pop_wm_learning_context_block_for_prompt() == ""


def test_degeneration_surprise_queues_prompt_block(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_REPLAN_CTX", "1")
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "0")
    monkeypatch.setenv("MIMIR_WM_VOE_RECALL", "0")
    reset_pending_wm_learning_context_for_test()
    from agent.degeneration_guard import DegenerationGuard

    DegenerationGuard().run_checks(
        expected_vs_actual=("operation success", "operation failed")
    )
    block = pop_wm_learning_context_block_for_prompt()
    assert "operation success" in block
    assert pop_wm_learning_context_block_for_prompt() == ""
