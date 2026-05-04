import threading
import time

from agent.tool_registry import ToolRegistry


def _register_many(reg: ToolRegistry, prefix: str, start: int, count: int) -> None:
    for i in range(start, start + count):
        name = f"{prefix}_{i}"
        reg.register(
            name=name,
            category="test",
            description="desc",
            schema={"type": "object", "properties": {}},
        )


def test_tool_registry_concurrent_register_and_get(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)

    threads: list[threading.Thread] = []
    threads.append(threading.Thread(target=_register_many, args=(reg, "t", 0, 25)))
    threads.append(threading.Thread(target=_register_many, args=(reg, "t", 25, 25)))
    threads.append(threading.Thread(target=_register_many, args=(reg, "u", 0, 25)))
    threads.append(threading.Thread(target=_register_many, args=(reg, "u", 25, 25)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Spot-check a few registrations.
    assert reg.get("t_0") is not None
    assert reg.get("t_49") is not None
    assert reg.get("u_0") is not None
    assert reg.get("u_49") is not None


def test_tool_registry_concurrent_visibility_toggles_and_unregister(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    name = "flip_tool"
    reg.register(
        name=name,
        category="test",
        description="flip visibility",
        schema={"type": "object", "properties": {}},
    )

    stop = threading.Event()
    seen_enabled = {"yes": False}
    seen_disabled = {"yes": False}
    lock = threading.Lock()
    # Both threads must be running before the race; otherwise the flipper can
    # finish all toggles while the reader never gets a slice (scheduler flake).
    both_live = threading.Barrier(2)

    def reader() -> None:
        both_live.wait()
        while not stop.is_set():
            row = reg.get(name)
            with lock:
                if row is None:
                    seen_disabled["yes"] = True
                else:
                    seen_enabled["yes"] = True
            # Tight spin would starve the flipper on CPython (GIL); yield so both
            # sides interleave and get() can observe enabled=1 between toggles.
            time.sleep(0)

    def flipper() -> None:
        both_live.wait()
        for _ in range(80):
            reg.disable(name)
            time.sleep(0)  # widen window so reader can observe enabled=1
            reg.enable(name)
            time.sleep(0)
        reg.disable(name)

    t_reader = threading.Thread(target=reader)
    t_flipper = threading.Thread(target=flipper)
    t_reader.start()
    t_flipper.start()
    t_flipper.join()
    stop.set()
    t_reader.join()

    assert seen_enabled["yes"] is True
    assert seen_disabled["yes"] is True
    assert reg.get(name) is None
    assert all(r["name"] != name for r in reg.search("flip_tool"))

    assert reg.unregister(name) is True
    assert reg.unregister(name) is False
    assert all(r["name"] != name for r in reg.list_all(enabled_only=False))

