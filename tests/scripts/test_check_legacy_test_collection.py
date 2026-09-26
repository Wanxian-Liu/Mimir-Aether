"""U10b：tests/legacy 零收集漂移哨兵的行为级用例（2026-09-26）。

被测对象：`scripts/check_legacy_test_collection.py`

为什么这些臂存在 —— `tests/legacy` 自带 `conftest.py` 的
`collect_ignore_glob = ["*.py"]`，整目录**静默不收集**（9 个 .py 文件、0 条在跑）。
停放是有意设计，但结构与 U10「注释覆盖」同形：**看着有测试，实际没有一条在跑**。

该哨兵的设计约束是「**不常驻报红**」——恒红会训练人忽略门禁（同族病：
恒红 / 假红 / 注释覆盖）。所以用例必须同时证明两件事：

  · 坏样本必拦：停放区清单漂移 ⇒ FAIL
  · 孪生不误拦：清单一致 / 收集>0 / 空目录 / 非停放环境 ⇒ PASS
  · **不能判定 ≠ PASS**：基线缺失/损坏、pytest 收集报错 ⇒ ERROR（自体检）

既有的 18/18 夹具全过却漏掉真实缺口，是本仓反复出现的教训（R6 的「文档示例」
一类未被夹具建模）⇒ 因此这里带**真实对象臂**（真跑 pytest 收集，读真实停放区）。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_legacy_test_collection.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_legacy_test_collection", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*extra: str, timeout: int = 300):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra],
        capture_output=True, text=True, timeout=timeout, cwd=str(REPO),
    )


# ---------------------------------------------------------------- 纯函数判据臂

def test_arm_baseline_match_passes():
    mod = _load()
    inv = {"a_test.py": "sha1"}
    verdict, hints = mod.assess(inv, 0, {"files": dict(inv)})
    assert verdict == "PASS", hints


def test_arm_new_file_fails_with_name():
    mod = _load()
    old = {"a_test.py": "sha1"}
    new = {"a_test.py": "sha1", "sneaky_test.py": "sha2"}
    verdict, hints = mod.assess(new, 0, {"files": old})
    assert verdict == "FAIL"
    assert any("sneaky_test.py" in h for h in hints), hints


def test_arm_changed_content_fails():
    mod = _load()
    old = {"a_test.py": "sha1"}
    new = {"a_test.py": "sha-CHANGED"}
    verdict, hints = mod.assess(new, 0, {"files": old})
    assert verdict == "FAIL"
    assert any("改动" in h for h in hints), hints


def test_arm_removed_file_fails():
    mod = _load()
    old = {"a_test.py": "sha1", "b_test.py": "sha2"}
    new = {"a_test.py": "sha1"}
    verdict, hints = mod.assess(new, 0, {"files": old})
    assert verdict == "FAIL"
    assert any("删除" in h and "b_test.py" in h for h in hints), hints


def test_twin_collected_positive_passes():
    """孪生：文件真的会跑 ⇒ 不是停放态，不该报。"""
    mod = _load()
    inv = {"a_test.py": "sha1"}
    verdict, _ = mod.assess(inv, 7, {"files": {}})
    assert verdict == "PASS"


def test_twin_empty_park_passes():
    mod = _load()
    verdict, _ = mod.assess({}, 0, {"files": {"x": "y"}})
    assert verdict == "PASS"


def test_arm_missing_baseline_is_self_health_error():
    """**坏样本**：基线缺失 = 判不了漂移 ⇒ ERROR。

    旧实现返回 PASS 并声称「本次记录」，但 main() 只在 --update-baseline 时写盘
    ⇒ 基线一旦丢失就**永久静默 PASS**（同族病：仪器死了读数像好消息）。
    """
    mod = _load()
    verdict, hints = mod.assess({"a_test.py": "sha1"}, 0, None)
    assert verdict == "ERROR", hints
    assert any("SELF-HEALTH" in h for h in hints), hints


def test_arm_corrupt_baseline_is_self_health_error():
    """**坏样本**：基线结构损坏（files 不是 dict）⇒ ERROR，不得读成 PASS。"""
    mod = _load()
    verdict, hints = mod.assess({"a_test.py": "sha1"}, 0, {"files": "not-a-dict"})
    assert verdict == "ERROR", hints
    assert any("SELF-HEALTH" in h for h in hints), hints


def test_collection_failure_is_error_not_pass():
    """仪器跑不动 ⇒ ERROR，**不得读成 0**（假绿族）。"""
    mod = _load()
    verdict, _ = mod.assess({"a_test.py": "sha1"}, None, {"files": {}})
    assert verdict == "ERROR"


def test_real_pytest_error_is_not_read_as_zero(tmp_path: Path):
    """**行为级**（旧用例只喂合成 None，没考到 collect_count 的接线）：

    pytest 退出码 2（收集报错）必须 ⇒ None；退出码 5（无测试被收集）才是合法 0。
    """
    mod = _load()
    park = tmp_path / "broken_park"
    park.mkdir()
    (park / "broken_test.py").write_text("def test_x(:\n    pass\n", encoding="utf-8")
    assert mod.collect_count(tmp_path, "broken_park") is None, "收集报错不得读成 0"

    ok = tmp_path / "empty_park"
    ok.mkdir()
    (ok / "conftest.py").write_text('collect_ignore_glob = ["*.py"]\n', encoding="utf-8")
    (ok / "a_test.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    assert mod.collect_count(tmp_path, "empty_park") == 0, "rc=5（无测试被收集）应为合法 0"


# ------------------------------------------------------- 受控双测（脚本内 selftest）

def test_selftest_arms_all_pass():
    proc = _run("--selftest")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST: PASS" in proc.stdout


# ---------------------------------------------------------------- 真实对象臂

def test_real_object_parked_state_is_zero_collection():
    """真实停放区：有 .py 文件、pytest 收集 0（这是本哨兵存在的理由）。"""
    mod = _load()
    inv = mod.inventory(REPO / "tests" / "legacy")
    assert len(inv) > 0, "停放区应有 .py 文件；为 0 说明目录被移走，本哨兵需重新定位"
    assert mod.collect_count(REPO, "tests/legacy") == 0


def test_real_object_end_to_end_pass_then_drift_fails(tmp_path: Path):
    """端到端：真实停放区副本 —— 先 PASS，加一个文件后 FAIL（负控受控差分）。"""
    park = tmp_path / "park"
    shutil.copytree(REPO / "tests" / "legacy", park,
                    ignore=shutil.ignore_patterns("__pycache__"))
    base = tmp_path / "baseline.json"
    common = ["--repo", str(tmp_path), "--park", str(park), "--baseline", str(base)]

    first = _run(*common, "--update-baseline")
    # 首跑无基线 ⇒ 判不了（自体检），但**登记动作必须真的发生**（旧实现两条都不成立）
    assert first.returncode == 2, first.stdout + first.stderr
    assert "SELF-HEALTH" in first.stdout
    assert "基线已写入" in first.stdout
    assert json.loads(base.read_text(encoding="utf-8"))["files"], "基线应为非空"

    stable = _run(*common)
    assert stable.returncode == 0, stable.stdout + stable.stderr
    assert "既定态" in stable.stdout

    (park / "zz_drift_test.py").write_text("def test_z():\n    assert True\n", encoding="utf-8")
    drifted = _run(*common)
    assert drifted.returncode == 1, drifted.stdout + drifted.stderr
    assert "VERDICT: FAIL" in drifted.stdout
    assert "zz_drift_test.py" in drifted.stdout

    # 漂移时 --update-baseline 必须真的登记（旧实现静默无操作），并明说是登记漂移
    rebased = _run(*common, "--update-baseline")
    assert rebased.returncode == 1, rebased.stdout + rebased.stderr
    assert "基线已写入" in rebased.stdout, rebased.stdout
    assert "承认" in rebased.stdout, rebased.stdout

    after = _run(*common)
    assert after.returncode == 0 and "既定态" in after.stdout, after.stdout + after.stderr


def test_cli_corrupt_baseline_is_self_health_fail(tmp_path: Path):
    """CLI 层：基线损坏 ⇒ 退出码 2 + 二值 VERDICT 契约不破 + SELF-HEALTH 明示。"""
    base = tmp_path / "corrupt.json"
    base.write_text("{ this is not json", encoding="utf-8")
    proc = _run("--baseline", str(base))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "VERDICT: FAIL" in proc.stdout or "VERDICT: FAIL" in proc.stderr
    assert "SELF-HEALTH" in (proc.stdout + proc.stderr)


def test_cli_missing_baseline_does_not_claim_to_record(tmp_path: Path):
    """**旧谎话**：提示写「本次记录」，但盘上什么都没写 ⇒ 现改为 SELF-HEALTH 并真的不假装记录。"""
    base = tmp_path / "absent.json"
    proc = _run("--baseline", str(base))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not base.exists(), "未加 --update-baseline 时不得偷偷建基线"
    assert "本次记录" not in proc.stdout


def test_real_object_gate_wiring():
    """接线守卫：mech_checks registry 必须真的登记了本项，且为 low severity
    （不直发飞书 ⇒ 提示级，不是门禁级）。"""
    reg_path = Path.home() / ".mimiraether" / "data" / "ops" / "mech_checks.json"
    if not reg_path.exists():
        import pytest
        pytest.skip("registry 不在本机（非生产环境）")
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    items = {it["id"]: it for it in reg.get("items", [])}
    assert "legacy_test_collection" in items, sorted(items)
    item = items["legacy_test_collection"]
    assert item.get("severity") == "low"
    assert "check_legacy_test_collection.py" in item.get("cmd", "")
