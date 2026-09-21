"""A9 边界负控（Loki debug ①）：字面 % + 空参数"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from scripts.report_template import raise_safe  # noqa: E402


def test_literal_percent_empty_args_degrades():
    """字面 % + 空参数：应降级为原样模板·不抛 TypeError"""
    with pytest.raises(ValueError) as ei:
        raise_safe(ValueError, '错误: 100%s done')
    assert '100%s done' in str(ei.value)  # 原样模板保留


def test_normal_render():
    with pytest.raises(ValueError) as ei:
        raise_safe(ValueError, 'db not found: %s', '/x/y')
    assert '/x/y' in str(ei.value)


def test_mismatch_degrades():
    """参数与占位符个数不匹配：降级 <args:>·不二次崩溃"""
    with pytest.raises(ValueError) as ei:
        raise_safe(ValueError, 'two: %s %s', 'only_one')
    assert '<args:' in str(ei.value)


def test_cause_chain():
    with pytest.raises(RuntimeError) as ei:
        raise_safe(RuntimeError, 'wrap: %s', 'x', cause=KeyError('k'))
    assert isinstance(ei.value.__cause__, KeyError)
