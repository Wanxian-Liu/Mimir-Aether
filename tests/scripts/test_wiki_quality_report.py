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
