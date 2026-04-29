import threading

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

