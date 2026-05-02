"""M4 minimal slice: offline tests for auxiliary HTTP error classification.

Maps to ``docs/ralph_roadmap_milestones.md`` M4 — no network, no API keys.
"""

from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APITimeoutError

from agent.auxiliary_client import _is_connection_error, _is_payment_error


def _dummy_request() -> httpx.Request:
    return httpx.Request("GET", "https://example.com/")


class TestIsPaymentError:
    def test_402_is_payment(self) -> None:
        exc = SimpleNamespace(status_code=402)
        assert _is_payment_error(exc) is True

    def test_401_not_payment(self) -> None:
        class E401(Exception):
            status_code = 401

        assert _is_payment_error(E401("invalid api key")) is False

    def test_429_without_billing_keywords_not_payment(self) -> None:
        class E429(Exception):
            status_code = 429

        assert _is_payment_error(E429("too many requests")) is False

    def test_429_with_credits_message_is_payment(self) -> None:
        class E429(Exception):
            status_code = 429

        assert _is_payment_error(E429("You have insufficient credits")) is True

    def test_none_status_with_billing_hint_is_payment(self) -> None:
        assert _is_payment_error(RuntimeError("payment required for this model")) is True


class TestIsConnectionError:
    def test_api_timeout_error(self) -> None:
        assert _is_connection_error(APITimeoutError(request=_dummy_request())) is True

    def test_api_connection_error(self) -> None:
        exc = APIConnectionError(message="connection failed", request=_dummy_request())
        assert _is_connection_error(exc) is True

    def test_substring_timed_out(self) -> None:
        assert _is_connection_error(RuntimeError("read operation timed out")) is True

    def test_substring_connection_refused(self) -> None:
        assert _is_connection_error(OSError("connection refused")) is True

    def test_plain_401_not_connection(self) -> None:
        class E401(Exception):
            status_code = 401

        assert _is_connection_error(E401("Unauthorized")) is False
