"""HERM-SCR-01: streaming think-block scrubber state machine."""

from __future__ import annotations

from agent.think_scrubber import StreamingThinkScrubber, strip_think_blocks


def test_partial_open_tag_held_across_chunks() -> None:
    s = StreamingThinkScrubber()
    assert s.feed("<redacted_thin") == ""
    assert s.feed("king>secret") == ""
    assert s.feed("</think>hi") == "hi"


def test_block_split_across_chunks() -> None:
    s = StreamingThinkScrubber()
    assert s.feed("pre\n") == "pre\n"
    # Open tag only stripped at line boundary (not mid-line prose).
    assert s.feed("<thinking>") == ""
    assert s.feed("reason") == ""
    assert s.feed("</thinking>") == ""
    assert s.feed(" post") == " post"


def test_flush_emits_held_partial_non_tag() -> None:
    s = StreamingThinkScrubber()
    assert s.feed("hello <thi") == "hello "
    assert s.flush() == "<thi"


def test_empty_block_removed() -> None:
    s = StreamingThinkScrubber()
    out = s.feed("<thinking></thinking>visible")
    assert out == "visible"
    assert s.flush() == ""


def test_reasoning_scratchpad_case_sensitive_tag() -> None:
    s = StreamingThinkScrubber()
    out = s.feed("<REASONING_SCRATCHPAD>x</REASONING_SCRATCHPAD>ok")
    assert out == "ok"


def test_strip_think_blocks_one_shot_matches_streaming() -> None:
    raw = "a<thinking>b</thinking>c"
    streamed = StreamingThinkScrubber()
    parts = [streamed.feed(raw), streamed.flush()]
    assert strip_think_blocks(raw) == "".join(parts)


def test_reset_clears_in_block_state() -> None:
    s = StreamingThinkScrubber()
    s.feed("<thinking>still inside")
    s.reset()
    assert s.feed("visible") == "visible"
