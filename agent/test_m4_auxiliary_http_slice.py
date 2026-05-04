"""M4 minimal slice: offline tests for auxiliary HTTP error classification.

Maps to ``docs/ralph_roadmap_milestones.md`` M4 — no network, no API keys.
Fixture-driven cases load ``fixtures/m4_http/error_shapes.json`` (see that README).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APITimeoutError

from agent.auxiliary_client import _is_connection_error, _is_payment_error

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_JSON = _REPO_ROOT / "fixtures" / "m4_http" / "error_shapes.json"


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


def _exc_from_fixture(exc_spec: dict, request: httpx.Request) -> Exception:
    kind = exc_spec["kind"]
    if kind == "status_exception":
        code = int(exc_spec["status_code"])
        msg = str(exc_spec.get("message", ""))

        class DynamicExc(Exception):
            status_code = code

        return DynamicExc(msg)
    if kind == "message_only":
        return RuntimeError(str(exc_spec["message"]))
    if kind == "openai_api_timeout":
        return APITimeoutError(request=request)
    if kind == "openai_api_connection":
        return APIConnectionError(message="connection failed", request=request)
    raise ValueError(f"unknown fixture exc.kind: {kind}")


class TestFixtureJsonShapes:
    """Structured shapes from ``fixtures/m4_http/error_shapes.json`` (M4 产出物)."""

    def test_all_entries_match_classification(self) -> None:
        rows = json.loads(_FIXTURE_JSON.read_text(encoding="utf-8"))
        req = _dummy_request()
        for row in rows:
            eid = row["id"]
            exc = _exc_from_fixture(row["exc"], request=req)
            assert _is_payment_error(exc) is row["payment"], eid
            assert _is_connection_error(exc) is row["connection"], eid
