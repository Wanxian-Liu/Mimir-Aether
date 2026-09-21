#!/usr/bin/env python3
"""报告模板单一漏斗 —— 未替换占位符即报错（A2 · 格式符字面量 bug 第 3 次复发）。

根因（两种表现、同一处）：

  1. **静默泄漏（最危险）**：模板里写了 `%s` 却漏传参数 ⇒ Python **不报错**
     （没有 `%` 运算就没有任何校验），字面 `%s` 直接落进报告。
     实证：`~/.mimiraether/logs/n13_restart_window.log` 第 41 行。
  2. **崩溃**：模板含字面 `%（` 却又施加 `%` 运算 ⇒
     `ValueError: unsupported format character`（N3 脚本曾致崩）。

为什么前两次修不掉：每次都是在「某个脚本里改那一行」，而每个脚本都自带一份
`log()` / `logline()`，**下一支新探针又是一处新的漏传点**。所以本模块不是在
report 行上打补丁，而是把「模板 → 文本」收敛为**同一个函数**，把校验放在
不可绕过的单点上。

机制（不靠纪律，靠闸）：

  * 有参数 ⇒ 施加 `%`；`TypeError`/`ValueError` 统一包成
    `UnrenderedTemplateError`，带模板预览 ⇒ 直接指出哪一行写坏了。
  * 无参数 ⇒ 模板含任何格式符（`%%` 除外）**立即报错**。
    这一闸就是消灭「静默泄漏」的那一闸。
  * 「有参数」这一路**不再做残留复检**：`%` 运算自身保证所有格式符都被消费
    （漏参 / 多参 / 非法转换都会抛，已被上一层包成领域异常）。曾写过「渲染后
    再查一遍残留」的兜底，受控双探针实测**对「参数值里天然含 `%s`」的正样本
    误报** ⇒ 已删。残留检查统一交给整篇终检 `scan_placeholders()`。
  * `Report.write()` 落盘前对整篇做 `scan_placeholders()` 终检。

约定：**字面百分号一律写 `%%`**；外部捕获的文本（可能天然含 `%s`）走
`Report.raw()` 显式豁免（自动包进围栏，终检跳过围栏内文本）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Union

__all__ = [
    "UnrenderedTemplateError",
    "render",
    "scan_placeholders",
    "Report",
]

_CONVERSIONS = "diouxXeEfFgGcrsa"

# 旗标类**不含空格旗标**：`50% and` 这类散文里的「% + 空格 + a」不得被误判成 `% a`。
_FLAGS = r"[#0+\-]*"

# 模板侧：任意格式符，含 `%s` 型与 `%(name)s` 型、含 `%%` 转义。
_ANY_SPEC = re.compile(
    r"%\([^)]+\)[hlL]?[" + _CONVERSIONS + r"]"
    r"|%" + _FLAGS + r"\d*(?:\.\d+)?[hlL]?(?:[" + _CONVERSIONS + r"]|%)"
)

# 文档终检侧：**窄**集合，专为散文零假阳性设计。
#   命中：`%s` `%d` `%r` `%i` `%f`（可带旗标/宽度/精度）与 `%(name)s`
#   不命中：`89% of`（`%` 后是 o，不在集合）；`92.5% 完成`（`%` 后是空格 + CJK）
_DOC_SPEC = re.compile(
    r"%\([A-Za-z_][A-Za-z0-9_]*\)[sdrif]"
    r"|%" + _FLAGS + r"\d*(?:\.\d+)?[sdrif]"
)


class UnrenderedTemplateError(ValueError):
    """模板未渲染完 —— 占位符残留或格式非法。"""


def raise_safe(exc_type, template: str, *args, cause: BaseException | None = None):
    """异常构造单一漏斗（A9 · 刘哥批）：先安全渲染模板再抛出。

    防「raise 里 raise」——格式化参数异常时原异常被吞、只剩二次 TypeError。
    本函数内部不使用任何动态格式化：参数逐个 str() 兜底，构造永不失败。
    """
    try:
        message = template % args if args else template
    except Exception:
        parts = ", ".join(repr(a) for a in args)
        message = f"{template} <args: {parts}>"
    if cause is not None:
        raise exc_type(message) from cause
    raise exc_type(message)


def _preview(text: str, limit: int = 140) -> str:
    t = text.replace("\n", "\\n")
    return t if len(t) <= limit else t[:limit] + "…"


def render(template: str, *args, **kwargs) -> str:
    """把一行报告模板渲染成文本；**未替换的占位符即报错**。

    >>> render("- PID `%s`", "1234")
    '- PID `1234`'
    >>> render("完成度 100%%")
    '完成度 100%'
    >>> render("真的发到了 home 频道（`%s`）")   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    UnrenderedTemplateError: ...
    """
    if not isinstance(template, str):
        raise UnrenderedTemplateError(
            "模板必须是 str，收到 %s: %r" % (type(template).__name__, template)
        )

    if args or kwargs:
        payload = kwargs if kwargs else args
        try:
            out = template % payload
        except (TypeError, ValueError, KeyError, IndexError) as e:
            raise UnrenderedTemplateError(
                "模板渲染失败（%s: %s）｜模板=%r" % (type(e).__name__, e, _preview(template))
            ) from e
    else:
        leaked = sorted({s for s in _ANY_SPEC.findall(template) if s != "%%"})
        if leaked:
            raise UnrenderedTemplateError(
                "模板含未替换占位符 %s 却未传参数 ⇒ 原样落盘即写入字面量｜模板=%r"
                % (leaked, _preview(template))
            )
        out = template.replace("%%", "%")

    return out


def scan_placeholders(text: str, *, context: str = "", skip_fenced: bool = True) -> List[str]:
    """整篇终检：返回命中的占位符描述（空列表 = 干净）。"""
    hits: List[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if skip_fenced and in_fence:
            continue
        for m in _DOC_SPEC.finditer(line):
            prefix = (context + ": ") if context else ""
            hits.append("%s%s ⟵ %s" % (prefix, m.group(0), line.strip()[:90]))
    return hits


@dataclass
class Report:
    """报告的单一漏斗：所有模板行走 `line()`，落盘走 `write()`。"""

    lines: List[str] = field(default_factory=list)

    def line(self, template: str = "", *args, **kwargs) -> "Report":
        """追加一行（走 `render()` ⇒ 未替换占位符当场报错）。"""
        self.lines.append(render(template, *args, **kwargs))
        return self

    def raw(self, text) -> "Report":
        """显式豁免：外部捕获文本原样入报告（包进围栏，终检跳过）。"""
        self.lines.append("```")
        for ln in (str(text).splitlines() or [""]):
            self.lines.append(ln)
        self.lines.append("```")
        return self

    def extend(self, items: Iterable) -> "Report":
        """批量追加**已渲染**的行（不施加模板语义）。"""
        self.lines.extend(str(i) for i in items)
        return self

    def text(self) -> str:
        return "\n".join(self.lines)

    def check(self) -> "Report":
        hits = scan_placeholders(self.text())
        if hits:
            raise UnrenderedTemplateError(
                "整篇终检发现未替换占位符：\n  " + "\n  ".join(hits)
            )
        return self

    def write(self, path: Union[str, Path], *, encoding: str = "utf-8") -> Path:
        """**先终检后落盘** —— 含未替换占位符则拒绝写入（不产出半成品文件）。"""
        self.check()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.text() + "\n", encoding=encoding)
        return p

    def emit(self) -> "Report":
        """渲染后打印（探针 stdout 通道），打印前同样终检。"""
        self.check()
        print(self.text(), flush=True)
        return self


def _selftest() -> int:
    import doctest
    fails, tests = doctest.testmod()
    print("doctest: %d 项 / 失败 %d" % (tests, fails), flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
