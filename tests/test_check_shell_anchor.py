"""部署侧脚本锚回归用例 —— 台账 T-A3（2026-11-07）。

病灶：`~/.mimiraether/scripts/*` 不进版本控制，cron 壳是门禁的搬运层——
  被改 / 被改回去，`git diff` 里什么都看不到。锚 = 仓库内 JSON，改动才可见。

本文件钉三件：
① 纯判据两向：匹配 ⇒ 0；哈希变 / 文件没了 ⇒ 1；锚为空表 ⇒ 0（不恒红）
② schema 两向：好 schema 过；坏长度 / 缺 path / 重复 ⇒ 拦（rc 语义归 2）
③ 端到端真文件：改一字节必翻红、还原必转绿（防「双绿 = 检测器已死」）
另加一条「活体契约」：真实锚清单与真实在跑脚本必须一致（不一致 ⇒ 有人改了在跑版
  却没 --update，正是本闸要拦的事）。CI 上没有该文件 ⇒ 跳过，不误报。
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_shell_anchor as anc  # noqa: E402

H1 = "a" * 64
H2 = "b" * 64


# ---------- ① 纯判据 ----------

def test_match_is_clean():
    rc, lines = anc.evaluate([{"path": "~/.x", "sha256": H1}], {"~/.x": H1})
    assert rc == 0
    assert lines[0] == "anchors=1 drift=0 missing=0"


def test_changed_hash_is_drift_and_names_file():
    rc, lines = anc.evaluate([{"path": "~/.x", "sha256": H1}], {"~/.x": H2})
    assert rc == 1
    assert "DRIFT changed" in "\n".join(lines)
    assert "~/.x" in "\n".join(lines), "漂移必须点名文件，否则无法处置"


def test_missing_file_is_drift_not_clean():
    rc, lines = anc.evaluate([{"path": "~/.x", "sha256": H1}], {"~/.x": None})
    assert rc == 1
    assert "DRIFT missing" in "\n".join(lines)


def test_empty_manifest_is_clean_not_red():
    """空锚表 ⇒ rc=0。恒红的闸会被忽略（本机 swap 闸同族教训）。"""
    rc, lines = anc.evaluate([], {})
    assert rc == 0 and lines[0] == "anchors=0 drift=0 missing=0"


def test_uppercase_manifest_hash_still_matches():
    """锚里存了大写 hex 也不得误报（大小写不是漂移）。"""
    rc, _ = anc.evaluate([{"path": "~/.x", "sha256": H1.upper()}], {"~/.x": H1})
    assert rc == 0


# ---------- ② schema ----------

def test_schema_accepts_good_entry():
    assert anc.validate_entries([{"path": "~/.x", "sha256": H1}]) == []


@pytest.mark.parametrize("entries", [
    [{"path": "~/.x", "sha256": "abc"}],        # 长度不够
    [{"sha256": H1}],                           # 缺 path
    [{"path": "~/.x", "sha256": H1}] * 2,       # 重复路径
    {"path": 1},                                # 不是数组
])
def test_schema_rejects_bad(entries):
    assert anc.validate_entries(entries), "坏 schema 必须被拦（否则闸按错锚比）"


def test_bad_manifest_returns_rc2_not_rc1(tmp_path):
    """锚清单坏了 = 仪表故障（2），不得与「真漂移」（1）混为一类。"""
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"anchors": [{"path": "~/.x", "sha256": "abc"}]}), encoding="utf-8")
    entries, err = anc.load_manifest(m)
    assert entries is None and err


def test_missing_manifest_rc2(tmp_path):
    entries, err = anc.load_manifest(tmp_path / "nope.json")
    assert entries is None and "缺失" in err


# ---------- ③ 端到端真文件 ----------

def test_tamper_flips_red_then_restore_green(tmp_path):
    f = tmp_path / "s.sh"
    f.write_text("echo hi\n", encoding="utf-8")
    entries = [{"path": str(f), "sha256": anc.sha256_file(f)}]
    assert anc.evaluate(entries, anc.collect_actual(entries))[0] == 0

    f.write_text("echo hi\n# tampered\n", encoding="utf-8")
    rc, lines = anc.evaluate(entries, anc.collect_actual(entries))
    assert rc == 1, "改一个字节必须翻红"
    assert "DRIFT changed" in "\n".join(lines)

    f.write_text("echo hi\n", encoding="utf-8")
    assert anc.evaluate(entries, anc.collect_actual(entries))[0] == 0, "还原必须转绿"


# ---------- 活体契约：真锚 vs 真在跑脚本 ----------

def _manifest() -> dict:
    return json.loads(anc.DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def test_real_manifest_matches_deployed_scripts():
    """锚清单必须与真实在跑脚本一致。

    不一致有两种，都要人处理：改了在跑版没 --update（漏），或改了锚没提交（也漏）。
    CI / 无该文件的环境 ⇒ 跳过（不让异地环境假红）。
    """
    entries = _manifest()["anchors"]
    assert anc.validate_entries(entries) == [], "锚清单 schema 坏了"
    for e in entries:
        if not Path(anc.expand(e["path"])).exists():
            pytest.skip(f"该环境无部署侧文件：{e['path']}")
    rc, lines = anc.evaluate(entries, anc.collect_actual(entries))
    assert rc == 0, "在跑脚本与锚不符：\n" + "\n".join(lines)


def test_manifest_paths_are_tilde_not_absolute_home():
    """锚清单进公开仓库 ⇒ 路径禁写 home 绝对路径（个人信息闸同族）。"""
    for e in _manifest()["anchors"]:
        assert e["path"].startswith("~/"), f"路径必须写 ~ 而非绝对 home 路径：{e['path']}"
