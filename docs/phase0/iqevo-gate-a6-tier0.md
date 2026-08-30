# Gate A6 — tier0 三连（非 sandbox）

## Run 1 — 2026-05-26T12:57:17Z
=== Ralph Tier-0: Gate1 Syntax/Import ===
import_ok
=== Ralph Tier-0: Gate2 Parity Tests ===
........................................................................ [ 15%]
........................................................................ [ 31%]
........................................................................ [ 47%]
........................................................................ [ 63%]
........................................................................ [ 79%]
........................................................................ [ 95%]
......................                                                   [100%]
=============================== warnings summary ===============================
../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
    __import__('pkg_resources').declare_namespace(__name__)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb.google')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    __import__('pkg_resources').declare_namespace(__name__)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
    _EPOCH_DATETIME_NAIVE = datetime.datetime.utcfromtimestamp(0)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26: DeprecationWarning: There is no current event loop
    loop = asyncio.get_event_loop()

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67: DeprecationWarning: websockets.InvalidStatusCode is deprecated
    def _parse_ws_conn_exception(e: websockets.InvalidStatusCode):

../../.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6
  ~//.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

agent/test_m5_gateway_session_db_slice.py::test_session_store_append_dual_writes_sqlite
  ~//.local/lib/python3.12/site-packages/chromadb/api/collection_configuration.py:327: DeprecationWarning: legacy embedding function config: 'HashEmbeddingFunction' object has no attribute 'is_legacy'
    return json.dumps(create_collection_configuration_to_json(config, metadata))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
454 passed, 10 warnings in 78.88s (0:01:18)
=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ===
..                                                                       [100%]
2 passed in 1.84s
=== Advisory: .openclaw literals (non-blocking) ===
[ok] .openclaw literal scan: 6 matches (threshold 60)
=== Ralph Tier-0/1: PASS ===
**result:** PASS (exit 0)

## Run 2 — 2026-05-26T12:58:46Z
=== Ralph Tier-0: Gate1 Syntax/Import ===
import_ok
=== Ralph Tier-0: Gate2 Parity Tests ===
........................................................................ [ 15%]
........................................................................ [ 31%]
........................................................................ [ 47%]
........................................................................ [ 63%]
........................................................................ [ 79%]
........................................................................ [ 95%]
......................                                                   [100%]
=============================== warnings summary ===============================
../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
    __import__('pkg_resources').declare_namespace(__name__)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb.google')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    __import__('pkg_resources').declare_namespace(__name__)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
    _EPOCH_DATETIME_NAIVE = datetime.datetime.utcfromtimestamp(0)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26: DeprecationWarning: There is no current event loop
    loop = asyncio.get_event_loop()

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67: DeprecationWarning: websockets.InvalidStatusCode is deprecated
    def _parse_ws_conn_exception(e: websockets.InvalidStatusCode):

../../.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6
  ~//.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

agent/test_m5_gateway_session_db_slice.py::test_session_store_append_dual_writes_sqlite
  ~//.local/lib/python3.12/site-packages/chromadb/api/collection_configuration.py:327: DeprecationWarning: legacy embedding function config: 'HashEmbeddingFunction' object has no attribute 'is_legacy'
    return json.dumps(create_collection_configuration_to_json(config, metadata))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
454 passed, 10 warnings in 80.44s (0:01:20)
=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ===
..                                                                       [100%]
2 passed in 1.25s
=== Advisory: .openclaw literals (non-blocking) ===
[ok] .openclaw literal scan: 6 matches (threshold 60)
=== Ralph Tier-0/1: PASS ===
**result:** PASS (exit 0)

## Run 3 — 2026-05-26T13:00:16Z
=== Ralph Tier-0: Gate1 Syntax/Import ===
import_ok
=== Ralph Tier-0: Gate2 Parity Tests ===
........................................................................ [ 15%]
........................................................................ [ 31%]
........................................................................ [ 47%]
........................................................................ [ 63%]
........................................................................ [ 79%]
........................................................................ [ 95%]
......................                                                   [100%]
=============================== warnings summary ===============================
../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
    __import__('pkg_resources').declare_namespace(__name__)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/__init__.py:2: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb.google')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    __import__('pkg_resources').declare_namespace(__name__)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws.pb')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi.ws')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../../../usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350
  /usr/lib/python3/dist-packages/pkg_resources/__init__.py:2350: DeprecationWarning: Deprecated call to `pkg_resources.declare_namespace('lark_oapi')`.
  Implementing implicit namespace packages (as specified in PEP 420) is preferred to `pkg_resources.declare_namespace`. See https://setuptools.pypa.io/en/latest/references/keywords.html#keyword-namespace-packages
    declare_namespace(parent)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/pb/google/protobuf/internal/well_known_types.py:91: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
    _EPOCH_DATETIME_NAIVE = datetime.datetime.utcfromtimestamp(0)

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:26: DeprecationWarning: There is no current event loop
    loop = asyncio.get_event_loop()

../../.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67
  ~//.local/lib/python3.12/site-packages/lark_oapi/ws/client.py:67: DeprecationWarning: websockets.InvalidStatusCode is deprecated
    def _parse_ws_conn_exception(e: websockets.InvalidStatusCode):

../../.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6
  ~//.local/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

agent/test_m5_gateway_session_db_slice.py::test_session_store_append_dual_writes_sqlite
  ~//.local/lib/python3.12/site-packages/chromadb/api/collection_configuration.py:327: DeprecationWarning: legacy embedding function config: 'HashEmbeddingFunction' object has no attribute 'is_legacy'
    return json.dumps(create_collection_configuration_to_json(config, metadata))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
454 passed, 10 warnings in 78.66s (0:01:18)
=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ===
..                                                                       [100%]
2 passed in 1.49s
=== Advisory: .openclaw literals (non-blocking) ===
[ok] .openclaw literal scan: 6 matches (threshold 60)
=== Ralph Tier-0/1: PASS ===
**result:** PASS (exit 0)

