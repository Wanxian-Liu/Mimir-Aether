"""段3 单测：delegate 返回协议（K2——output_path 提取）"""
import sys, os, re
sys.path.insert(0, os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.delegate_tool import _build_child_system_prompt


def test_prompt_has_output_path_marker():
    """子代理 prompt 必须含 OUTPUT_PATH 要求（K2）"""
    prompt = _build_child_system_prompt(goal="测试任务", context=None)
    assert "OUTPUT_PATH=<abs path>" in prompt


def test_output_path_extract():
    """summary 含 OUTPUT_PATH → 提取成功"""
    summary = "完成了任务。\nOUTPUT_PATH=/tmp/result.json\n下一步..."
    m = re.search(r"OUTPUT_PATH[=:]\s*(.+)$", summary, re.MULTILINE)
    assert m is not None
    assert m.group(1).strip() == "/tmp/result.json"


def test_output_path_extract_none():
    """summary 无 OUTPUT_PATH → None（默认）"""
    summary = "完成了任务，没有产物文件。"
    m = re.search(r"OUTPUT_PATH[=:]\s*(.+)$", summary, re.MULTILINE)
    assert m is None


def test_output_path_multi_line():
    """多行 OUTPUT_PATH（每行一个）——至少提取第一个"""
    summary = "OUTPUT_PATH=/tmp/a.json\nOUTPUT_PATH=/tmp/b.json"
    paths = re.findall(r"OUTPUT_PATH[=:]\s*(.+)$", summary, re.MULTILINE)
    assert len(paths) == 2


def test_output_path_multi_line_aligned_with_production():
    """缺口B修复（2026-08-20 Mimir验证）：生产用 re.search 只取第一个——测试对齐"""
    summary = "OUTPUT_PATH=/tmp/a.json\nOUTPUT_PATH=/tmp/b.json"
    m = re.search(r"OUTPUT_PATH[=:]\s*(.+)$", summary, re.MULTILINE)
    assert m is not None
    assert m.group(1).strip() == "/tmp/a.json"  # 只取第一个（与生产 _run_single_child 一致）


def test_output_path_exists_field():
    """缺口A修复验证：output_path_exists 字段逻辑（存在/不存在）"""
    import os, tempfile
    # 存在的路径
    with tempfile.NamedTemporaryFile(suffix=".json") as tf:
        p = tf.name
        assert os.path.exists(p) is True
    # 不存在的路径
    assert os.path.exists("/tmp/definitely_not_exist_xyz.json") is False
