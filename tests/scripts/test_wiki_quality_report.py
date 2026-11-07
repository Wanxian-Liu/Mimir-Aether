"""B2 script 形态：wiki 质量门禁报告层的行为级用例（2026-09-26）。

被测对象：`scripts/wiki_quality_report.py`（零 LLM）。
为什么这些臂存在 —— 旧门禁（home 侧 wiki-quality-gate.sh）有三类**稳定假阳性**，
它们让「每天报红」变成噪声，而噪声会训练人忽略门禁（同族：恒红/假红/注释覆盖）：

  1. 扫所有文件（不限 .md）        => 非 md 里的 bash [[ ]] 被当 wikilink
  2. 不跳代码块 / 行内代码          => 文档里举例的链接被当死链
  3. glob `-name "*-*.md"` 判重    => 漏「空格 vs 连字符」同页变体，且把 README/index 报成重复

因此每个判据都配**反臂**（该报的不漏、不该报的不报），而不是只测「跑得过」。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "wiki_quality_report.py"


def _load():
    spec = importlib.util.spec_from_file_location("wiki_quality_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "entities").mkdir(parents=True)
    (wiki / "SCHEMA.md").write_text("---\ntitle: Schema\n---\n# Schema\n", encoding="utf-8")
    return wiki


def _run(wiki: Path, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--wiki", str(wiki), "--json", str(wiki / "out.json"), *extra],
        capture_output=True, text=True, timeout=300,
    )


# ---------------------------------------------------------------- 作用域（代码）

def test_strip_code_keeps_line_numbers(tmp_path):
    mod = _load()
    text = "a\n```python\n[[not-a-link]]\n```\nb\n`[[inline]]` c\n"
    out = mod.strip_code(text)
    assert out.count("\n") == text.count("\n"), "行结构必须保持（行号是溯源判据）"
    assert "not-a-link" not in out
    assert "[[inline]]" not in out


def test_fenced_example_is_not_broken(tmp_path):
    """反臂 1：文档里举例说明的链接不算死链（旧门禁在此稳定误报）。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "doc.md").write_text(
        "# d\n\n```markdown\n[[no-such-page]]\n```\n", encoding="utf-8")
    r = _run(wiki)
    assert r.returncode == 0
    assert "无问题" in r.stdout, r.stdout


def test_inline_code_example_is_not_broken(tmp_path):
    """反臂 2：行内代码里的链接形态同样不算死链。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "doc.md").write_text(
        "# d\n\n写法是 `[[no-such-page]]` 这样。\n", encoding="utf-8")
    assert "无问题" in _run(wiki).stdout


def test_real_broken_link_is_flagged_with_line(tmp_path):
    """正臂：真死链必须报，且行号准确。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "p.md").write_text("# p\n\nline2\nline3\n参见 [[missing-page]]\n", encoding="utf-8")
    r = _run(wiki)
    assert "死链 1 条" in r.stdout, r.stdout
    assert "p.md:5" in r.stdout, r.stdout


def test_alias_and_anchor_forms(tmp_path):
    """别名取 target、锚点去掉、纯锚点跳过。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "target-page.md").write_text("# t\n", encoding="utf-8")
    (wiki / "entities" / "p.md").write_text(
        "# p\n\n[[target-page|显示名]]\n[[target-page#sec]]\n[[#anchor]]\n", encoding="utf-8")
    assert "无问题" in _run(wiki).stdout


def test_placeholder_example_is_filtered_and_counted(tmp_path):
    """[[file#x]] 这类语法举例被过滤，且条数写进报告（过滤不可隐形）。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "r.md").write_text(
        "# r\n\n| section anchors（[[#x]] + [[file#x]]）| 7 |\n", encoding="utf-8")
    r = _run(wiki)
    assert "placeholder" not in r.stdout
    assert "无问题" in r.stdout
    payload = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    # 只有 [[file#x]] 计占位符；[[#x]] 是纯锚点，由另一条规则（anchor）跳过，不重复计
    assert payload["placeholder_skipped"] == 1, payload["placeholder_skipped"]


def test_resolution_scope_covers_wiki_root(tmp_path):
    """解析面 != 扫描面：链到 wiki 根的非策展层页面是合法链接。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "p.md").write_text("# p\n\n参见 [[SCHEMA]]\n", encoding="utf-8")
    r = _run(wiki)
    assert "无问题" in r.stdout, r.stdout


# ---------------------------------------------------------------- 判重（作用域）

def test_same_dir_space_vs_hyphen_is_duplicate(tmp_path):
    """正臂：同目录「空格 vs 连字符」是同页重复 —— 旧 glob 抓不到这一类。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "1Q84 世界.md").write_text("# a\n", encoding="utf-8")
    (wiki / "concepts" / "1Q84-世界.md").write_text("# b\n", encoding="utf-8")
    r = _run(wiki)
    assert "同页重复 1 组" in r.stdout, r.stdout
    payload = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert payload["duplicate_groups"] == 1


def test_readme_per_dir_is_not_duplicate(tmp_path):
    """反臂 3：每目录约定名（README/index）不是重复页 —— 旧判据在此稳定误报 8 组。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "a").mkdir()
    (wiki / "concepts" / "b").mkdir()
    (wiki / "concepts" / "a" / "README.md").write_text("# a\n", encoding="utf-8")
    (wiki / "concepts" / "b" / "README.md").write_text("# b\n", encoding="utf-8")
    assert "无问题" in _run(wiki).stdout


def test_cross_layer_same_name_is_informational_only(tmp_path):
    """反臂 4：跨目录/跨层同名只作信息级，不计入问题。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "X.md").write_text("# c\n", encoding="utf-8")
    (wiki / "entities" / "X.md").write_text("# e\n", encoding="utf-8")
    r = _run(wiki)
    assert "无问题" in r.stdout, r.stdout
    payload = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert payload["duplicate_groups"] == 0
    assert payload["cross_dir_same_name"] == 0, "跨层同名不该进信息级（层不同≠同页）"
    assert payload["files_scanned"] == 2


def test_same_layer_two_dirs_is_informational(tmp_path):
    """信息级正臂：同层不同目录同名 -> 计入 cross，但不算问题。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "book-a").mkdir()
    (wiki / "concepts" / "book-b").mkdir()
    (wiki / "concepts" / "book-a" / "第1章.md").write_text("# a\n", encoding="utf-8")
    (wiki / "concepts" / "book-b" / "第1章.md").write_text("# b\n", encoding="utf-8")
    r = _run(wiki)
    assert "无问题" in r.stdout, r.stdout
    payload = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert payload["duplicate_groups"] == 0
    assert payload["cross_dir_same_name"] == 1


# ---------------------------------------------------------------- 退出码（仪表）

def test_clean_wiki_exits_zero(tmp_path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "ok.md").write_text("# ok\n\n[[SCHEMA]]\n", encoding="utf-8")
    assert _run(wiki).returncode == 0


def test_missing_wiki_dir_exits_two(tmp_path):
    """仪表故障必须显形：目录不存在 => 2（台账 error），不是「零问题」。"""
    r = _run(tmp_path / "nope")
    assert r.returncode == 2
    assert "无法运行" in r.stdout


def test_empty_layers_exit_two_and_do_not_claim_clean(tmp_path):
    """反臂 5：扫到 0 篇 .md 也不许说「无问题」——那正是假绿族的原型。"""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    r = _run(wiki)
    assert r.returncode == 2
    assert "无问题" not in r.stdout
    assert "仪表故障" in r.stdout


def test_strict_flag_turns_findings_into_exit_one(tmp_path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "p.md").write_text("# p\n\n参见 [[missing]]\n", encoding="utf-8")
    assert _run(wiki).returncode == 0
    assert _run(wiki, "--strict").returncode == 1


def test_json_artifact_records_scope_and_counts(tmp_path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "p.md").write_text("# p\n\n[[missing-a]]\n", encoding="utf-8")
    _run(wiki)
    payload = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    for key in ("files_scanned", "resolve_files", "broken_count", "duplicate_groups",
                "cross_dir_same_name", "placeholder_skipped", "layers_present", "layers_missing"):
        assert key in payload, key
    assert payload["layers_missing"], "未覆盖层必须披露（否则零问题会被外推）"


# ---------------------------------------------------------------- 前代对照（鉴别力）

def test_legacy_scope_would_have_flagged_the_sample(tmp_path):
    """受控差分：同一份样本，前代口径（扫全文、不跳代码）必然误报 —— 证明本修有鉴别力。

    这不是「顺便测个旧版」，而是把「修好了」与「本来就绿」区分开的唯一手段。
    """
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "doc.md").write_text(
        "# d\n\n```markdown\n[[no-such-page]]\n```\n", encoding="utf-8")

    # 前代口径：不做代码剥离
    legacy_hits = ["[[no-such-page]]"] if "[[no-such-page]]" in (wiki / "concepts" / "doc.md").read_text(encoding="utf-8") else []
    assert legacy_hits, "样本必须能被前代口径命中，否则本臂空转"

    # 当代口径：剥离代码后不再命中
    mod = _load()
    stripped = mod.strip_code((wiki / "concepts" / "doc.md").read_text(encoding="utf-8"))
    assert "[[no-such-page]]" not in stripped
    assert "无问题" in _run(wiki).stdout


# ------------------------------------------------- 盲区补丁（2026-09-29 双族命名整改）

def test_separator_shift_duplicate_is_detected(tmp_path):
    """位移变体（连字符位置不同）必须报 —— normalize 判据在此恒不相等（曾永久盲区）。

    实证来源：concepts/AERIS-10开源相控阵雷达.md vs concepts/aeris10-开源相控阵雷达.md
    """
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "AERIS-10开源相控阵雷达.md").write_text("---\ntitle: a\n---\nx\n", encoding="utf-8")
    (wiki / "concepts" / "aeris10-开源相控阵雷达.md").write_text("---\ntitle: b\n---\ny\n", encoding="utf-8")
    r = _run(wiki)
    assert r.returncode == 0, r.stderr
    data = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert data["duplicate_groups"] >= 1, "位移变体必须被报为同页重复"


def test_cross_dir_near_name_is_not_same_page_duplicate(tmp_path):
    """反臂：跨目录近名不算同页重复（防止把位移判据放宽成噪声源）。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "a-b.md").write_text("---\ntitle: a\n---\nx\n", encoding="utf-8")
    (wiki / "entities" / "ab.md").write_text("---\ntitle: b\n---\ny\n", encoding="utf-8")
    r = _run(wiki)
    assert r.returncode == 0, r.stderr
    data = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert data["duplicate_groups"] == 0, "跨目录近名不得计入同页重复"


def test_bare_path_target_broken_is_detected(tmp_path):
    """frontmatter relations.target 的裸路径失效必须报（曾完全不在门禁判据内）。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "x.md").write_text(
        "---\ntitle: X\nrelations:\n  - type: knows\n    target: entities/nope\n---\n# X\n",
        encoding="utf-8")
    r = _run(wiki)
    assert r.returncode == 0, r.stderr
    data = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert data["broken_targets_count"] == 1, "裸路径失效必须被报"
    assert data["broken_targets"][0]["target"] == "entities/nope"


def test_bare_path_target_valid_and_out_of_scope_are_not_reported(tmp_path):
    """反臂：目标存在 => 不报；解析面外前缀（raw/ 等）=> 跳过并计数。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "ok.md").write_text("---\ntitle: Ok\n---\n# Ok\n", encoding="utf-8")
    (wiki / "concepts" / "c.md").write_text(
        "---\ntitle: C\nrelations:\n  - type: knows\n    target: entities/ok\n"
        "  - type: src\n    target: raw/papers/whatever\n---\n# C\n",
        encoding="utf-8")
    r = _run(wiki)
    assert r.returncode == 0, r.stderr
    data = json.loads((wiki / "out.json").read_text(encoding="utf-8"))
    assert data["broken_targets_count"] == 0, "存在目标不得报；外域前缀应跳过"
    assert data["target_skipped"] == 1, "外域前缀跳过数必须被计数（不是静默）"


# ------------------------------------------- 解析面外的真文件（2026-09-29 同族假红）

def test_target_into_excluded_dir_is_skipped(tmp_path):
    """正控：指向 archive/ 下**真文件**的 relations.target 不得报断链。

    索引构建按「任一段 ∈ EXCLUDED_DIRS」排除，故 `llmvt/hermes/archive/old`
    永远解不出；旧判据只比前缀 ⇒ 真文件被报成断链（假红）。
    """
    wiki = _mk_wiki(tmp_path)
    (wiki / "llmvt" / "hermes" / "archive").mkdir(parents=True)
    (wiki / "llmvt" / "hermes" / "archive" / "old.md").write_text(
        "---\ntitle: old\n---\n", encoding="utf-8")
    (wiki / "entities" / "a.md").write_text(
        "---\ntitle: a\ntype: entity\nrelations:\n  - type: distilled\n"
        "    target: llmvt/hermes/archive/old\n---\n\n# a\n",
        encoding="utf-8")
    r = _run(wiki)
    assert "裸路径引用失效" not in r.stdout, r.stdout


def test_target_missing_still_flagged(tmp_path):
    """负控：真不存在的 target 仍须报出（不得因上条而静默）。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "a.md").write_text(
        "---\ntitle: a\ntype: entity\nrelations:\n  - type: relates\n"
        "    target: entities/never-existed\n---\n\n# a\n",
        encoding="utf-8")
    r = _run(wiki)
    assert "裸路径引用失效" in r.stdout, r.stdout


def test_wikilink_into_excluded_dir_is_skipped(tmp_path):
    """正控（① 侧）：`[[archive/old-file]]` 指向真文件 ⇒ 跳过而非死链。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "archive").mkdir(parents=True)
    (wiki / "concepts" / "archive" / "old-file.md").write_text(
        "---\ntitle: old\n---\n", encoding="utf-8")
    (wiki / "entities" / "b.md").write_text(
        "---\ntitle: b\ntype: entity\n---\n\n见 [[archive/old-file]]\n",
        encoding="utf-8")
    r = _run(wiki)
    assert "① 死链" not in r.stdout, r.stdout


def test_wikilink_missing_still_broken(tmp_path):
    """负控（① 侧）：真缺页仍须报死链。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "c.md").write_text(
        "---\ntitle: c\ntype: entity\n---\n\n见 [[nobody-here]]\n", encoding="utf-8")
    r = _run(wiki)
    assert "① 死链" in r.stdout, r.stdout


# ---------------------------------------------------------------- P0-2 解析面外裸名豁免
# 根因（2026-11-07 实测 42/46）：解析面排除 discussions/，而讨论卡是合法链接目标。
# 带路径形态靠 _has_excluded_component 豁免了，裸名形态没有路径段 ⇒ 豁免走不到。
# 同一语义两种写法只保护了一种 —— 这类「同族漏修」必须两向测，否则修一半又成假绿。


def _mk_wiki_with_discussion(tmp_path: Path) -> Path:
    """建一个「扫描面外有真卡」的临时 wiki。"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "discussions").mkdir(parents=True)
    (wiki / "discussions" / "2026-10-11-四方会议-真卡.md").write_text(
        "---\ntitle: x\n---\n# x\n", encoding="utf-8"
    )
    (wiki / "concepts" / "台账.md").write_text(
        "---\ntitle: t\n---\n\n[[2026-10-11-四方会议-真卡]]\n[[这个卡不存在-zzz]]\n",
        encoding="utf-8",
    )
    return wiki


def test_partition_exempts_bare_name_found_outside_surface(tmp_path):
    """POS：裸名指向 discussions/ 真卡 ⇒ 不算死链，且必须带 found 溯源。"""
    mod = _load()
    wiki = _mk_wiki_with_discussion(tmp_path)
    ext = mod.build_index(mod._iter_all_md_any(wiki))
    broken = [{"target": "2026-10-11-四方会议-真卡", "src": "x", "line": 1}]
    kept, exempt = mod.partition_outside_surface(broken, ext)
    assert kept == [], "面外真卡被误判为死链"
    assert len(exempt) == 1
    assert exempt[0]["found"].endswith("2026-10-11-四方会议-真卡.md"), "豁免项缺真实路径溯源"


def test_partition_keeps_truly_missing(tmp_path):
    """NEG：全库都不存在 ⇒ 仍判死链。豁免不能顺手把真问题吃掉。"""
    mod = _load()
    wiki = _mk_wiki_with_discussion(tmp_path)
    ext = mod.build_index(mod._iter_all_md_any(wiki))
    broken = [{"target": "这个卡不存在-zzz", "src": "x", "line": 2}]
    kept, exempt = mod.partition_outside_surface(broken, ext)
    assert exempt == []
    assert len(kept) == 1, "真死链被豁免吞掉"


def test_partition_path_form_still_not_double_counted(tmp_path):
    """回归：带路径形态（已由 _has_excluded_component 跳过）不该出现在死链输入里。"""
    mod = _load()
    wiki = _mk_wiki_with_discussion(tmp_path)
    files = mod._iter_md(wiki, mod.DEFAULT_LAYERS)
    index = mod.build_index(mod._iter_all_md(wiki))
    broken, _skipped = mod.find_broken_links(files, index)
    # 带路径的 discussions 链接在更早一步就被跳过，不会成为 candidate
    assert not [b for b in broken if str(b.get("target", "")).startswith("discussions/")]


def test_report_broadcasts_outside_exempt(tmp_path):
    """不静默臂：豁免必须出现在播报里（只做到「不报」= 假阳换静默，更坏）。"""
    mod = _load()
    wiki = _mk_wiki_with_discussion(tmp_path)
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--wiki", str(wiki), "--json", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "解析面外豁免 1 条/1 个目标" in proc.stdout, proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["outside_exempt_count"] == 1
    assert payload["outside_exempt_targets"] == ["2026-10-11-四方会议-真卡"]
    # 真死链仍被报出（豁免没有连带吃掉它）
    assert payload["broken_count"] == 1
    assert payload["broken"][0]["target"] == "这个卡不存在-zzz"


# ---------------------------------------------------------------- P0-1 问题计数 sidecar
# 病灶：cron 台账只有 last_status=ok/failed，而壳刻意让 rc=0（有无 issue 都算跑完）
# => 「跑完且干净」与「跑完但有 46 条死链」在台账里完全同形。
# 这两条臂必须一起测：只测「有问题写 N」会漏「没问题是 0」（那才是恒非零假绿）。


def test_issues_marker_counts_real_problems(tmp_path):
    """POS：有真死链 ⇒ marker ISSUES=1，且 BROKEN=1。"""
    mod = _load()
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "a.md").write_text(
        "---\ntitle: a\n---\n\n[[这个卡不存在-zzz]]\n", encoding="utf-8"
    )
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--wiki", str(wiki), "--json", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    marker = out.parent / (out.name + ".issues")
    assert marker.exists(), "sidecar 未写出"
    kv = dict(
        ln.split("=", 1) for ln in marker.read_text(encoding="utf-8").splitlines() if "=" in ln
    )
    assert kv["ISSUES"] == "1", kv
    assert kv["BROKEN"] == "1", kv


def test_issues_marker_zero_on_clean_wiki(tmp_path):
    """NEG：干净 wiki ⇒ ISSUES=0。防「恒非零」这种反向假绿。"""
    mod = _load()
    wiki = _mk_wiki(tmp_path)
    (wiki / "concepts" / "a.md").write_text("---\ntitle: a\n---\n\n[[a]]\n", encoding="utf-8")
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--wiki", str(wiki), "--json", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    marker = out.parent / (out.name + ".issues")
    kv = dict(
        ln.split("=", 1) for ln in marker.read_text(encoding="utf-8").splitlines() if "=" in ln
    )
    assert kv["ISSUES"] == "0", kv


def test_issues_marker_excludes_outside_exempt(tmp_path):
    """口径臂：面外豁免不计入 ISSUES（否则刚消掉的噪声又被算回来）。"""
    mod = _load()
    wiki = _mk_wiki_with_discussion(tmp_path)
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--wiki", str(wiki), "--json", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    marker = out.parent / (out.name + ".issues")
    kv = dict(
        ln.split("=", 1) for ln in marker.read_text(encoding="utf-8").splitlines() if "=" in ln
    )
    assert kv["ISSUES"] == "1", kv          # 只剩那条真死链
    assert kv["BROKEN"] == "1", kv
    assert kv["EXEMPT"] == "1", kv          # 豁免照实报数，只是不进 ISSUES
