"""Vision routing: text-only chat models must not be used for image_url payloads."""

from agent.auxiliary_client import _supports_openai_chat_vision_model


def test_deepseek_chat_not_vision_capable():
    assert _supports_openai_chat_vision_model("deepseek-chat") is False
    assert _supports_openai_chat_vision_model("deepseek/deepseek-chat") is False


def test_gemini_flash_vision_capable():
    assert _supports_openai_chat_vision_model("google/gemini-3-flash-preview") is True
