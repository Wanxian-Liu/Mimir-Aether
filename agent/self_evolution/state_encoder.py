"""
StateEncoder — JEPA Encoder for Code Architecture Domain

物理世界: 场景描述 → [m, x, y, vx, vy, ...]
代码世界: agent/ 文件集合 → 依赖图 + 约束图 + tier0状态

只读审计，不改任何文件。
"""

import ast
import time
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field

# ── 单源约束定义 (cost.py 也从这里导入，避免双源不一致) ──
PROTECTED_FILES = {
    "agent_core": ["__init__.py", "agent_loop.py", "turn_loop.py", "core_loop.py",
                   "types.py", "prompt_builder.py"],
    "gateway_interface": ["exec_mixin.py", "callers_mixin.py", "config_mixin.py",
                          "recovery_mixin.py"],
    "tool_registry": ["tool_registry.py", "tool_guard.py", "tool_port.py"],
}


@dataclass
class DependencyNode:
    """依赖节点"""
    file_path: str              # 相对 agent/ 的路径
    imports: List[str] = field(default_factory=list)        # 导入的模块
    imported_by: List[str] = field(default_factory=list)    # 被哪些模块导入
    n_lines: int = 0
    has_tests: bool = False


@dataclass
class CodebaseState:
    """代码库状态 — JEPA框架中的 's[t]'"""
    timestamp: float
    files: Dict[str, DependencyNode] = field(default_factory=dict)
    call_graph: Dict[str, List[str]] = field(default_factory=dict)     # file → [files it calls]
    reverse_call_graph: Dict[str, List[str]] = field(default_factory=dict)  # file → [files calling it]
    constraint_map: Dict[str, List[str]] = field(default_factory=dict)     # constraint → files under it
    tier0_status: Dict[str, str] = field(default_factory=dict)            # test_name → pass/fail
    total_lines: int = 0
    total_files: int = 0


class StateEncoder:
    """
    JEPA Encoder: agent/ 文件 → CodebaseState

    物理WM中Encoder把"球在10m高"编码为[5, 0, 10, 0]，
    这里把 agent/ 目录编码为依赖图 + 约束图 + tier0状态。
    """

    def __init__(self, agent_dir: Optional[str] = None):
        if agent_dir is None:
            agent_dir = str(Path(__file__).parent.parent)
        self.agent_dir = Path(agent_dir)
        self._cached_state: Optional[CodebaseState] = None
        self._cached_at: float = 0

    # 模块级 tier0 缓存 — 跨实例共享
    _tier0_module_cache: Optional[Dict[str, Any]] = None
    _tier0_module_cache_at: float = 0

    def encode(self, force_refresh: bool = False, run_tier0: bool = False) -> CodebaseState:
        """编码当前代码库状态为 CodebaseState
        
        Args:
            force_refresh: 强制刷新缓存
            run_tier0: 是否运行 tier0 脚本（慢，~35s）。默认 False 以保持快速响应。
        """
        # 如果文件系统有变更，自动失效缓存
        if self._cached_state and not force_refresh and (time.time() - self._cached_at < 60):
            # 检查 agent/ 下任一 .py 文件 mtime 是否晚于缓存时间
            cache_stale = False
            for py_file in self.agent_dir.rglob("*.py"):
                try:
                    if py_file.stat().st_mtime > self._cached_at:
                        cache_stale = True
                        break
                except OSError:
                    continue
            if cache_stale:
                self._cached_state = None
            else:
                return self._cached_state

        files = self._scan_files()
        state = CodebaseState(
            timestamp=time.time(),
            files=files,
            total_files=len(files),
            total_lines=sum(n.n_lines for n in files.values()),
        )

        # 构建调用图
        state.call_graph = self._build_call_graph(files)
        state.reverse_call_graph = self._build_reverse_graph(state.call_graph)

        # 构建约束图
        state.constraint_map = self._build_constraint_map(files)

        # 读取 tier0 状态（仅当显式请求时运行，否则用缓存或返回 unknown）
        if run_tier0:
            state.tier0_status = self._read_tier0_status()
        elif StateEncoder._tier0_module_cache:
            state.tier0_status = StateEncoder._tier0_module_cache
        else:
            state.tier0_status = {"_source": "lazy", "status": "not_run",
                                  "exit_code": -1, "summary": "tier0 not run (lazy), use run_tier0=True"}

        self._cached_state = state
        self._cached_at = time.time()
        return state

    # ── 内部方法 ──

    def _scan_files(self) -> Dict[str, DependencyNode]:
        """扫描 agent/ 下所有 .py 文件"""
        nodes: Dict[str, DependencyNode] = {}
        for py_file in sorted(self.agent_dir.rglob("*.py")):
            rel_path = str(py_file.relative_to(self.agent_dir))
            try:
                source = py_file.read_text()
                tree = ast.parse(source)
                imports = self._extract_imports(tree)
                lines = len(source.splitlines())
            except (SyntaxError, OSError):
                imports = []
                lines = 0

            nodes[rel_path] = DependencyNode(
                file_path=rel_path,
                imports=imports,
                n_lines=lines,
                has_tests=rel_path.startswith("test_") or "test_" in rel_path,
            )
        return nodes

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """提取 Python 文件的所有导入"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports

    def _build_call_graph(self, files: Dict[str, DependencyNode]) -> Dict[str, List[str]]:
        """构建 file → [files it imports from agent/] 调用图"""
        graph: Dict[str, List[str]] = {}
        for fpath, node in files.items():
            callers = []
            for imp in node.imports:
                # 只追踪 agent/ 内部的调用
                parts = imp.split(".")
                for i in range(len(parts)):
                    candidate = "/".join(parts[:i+1]) + ".py"
                    if candidate in files:
                        callers.append(candidate)
                        break
            graph[fpath] = callers
        return graph

    def _build_reverse_graph(self, call_graph: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """构建 reverse: file → [files calling it]"""
        reverse: Dict[str, List[str]] = {k: [] for k in call_graph}
        for caller, callees in call_graph.items():
            for callee in callees:
                if callee in reverse:
                    reverse[callee].append(caller)
        return reverse

    def _build_constraint_map(self, files: Dict[str, DependencyNode]) -> Dict[str, List[str]]:
        """约束图：哪些文件受保护不能随意改动。
        
        文件列表来自模块级常量 PROTECTED_FILES（单源），
        cost.py 也从这里导入，避免双源不一致。
        """
        constraints: Dict[str, List[str]] = {k: [] for k in PROTECTED_FILES}
        constraints["test_protected"] = []
        constraints["high_fan_out"] = []  # 被很多文件依赖的（动态计算）

        for fpath, node in files.items():
            for group, protected_list in PROTECTED_FILES.items():
                if fpath in protected_list:
                    constraints[group].append(fpath)

            if node.has_tests:
                constraints["test_protected"].append(fpath)

        return constraints

    def _read_tier0_status(self) -> Dict[str, str]:
        """读取 tier0 基线状态 — 实际运行脚本，缓存 300s"""
        import subprocess
        now = time.time()
        if StateEncoder._tier0_module_cache and (now - StateEncoder._tier0_module_cache_at) < 300:
            return StateEncoder._tier0_module_cache

        try:
            repo_root = self.agent_dir.parent
            tier0_script = repo_root / "run_ralph_tier0.sh"
            if not tier0_script.exists():
                return {"_source": "unknown", "status": "unknown",
                        "exit_code": -1, "summary": "tier0 script not found"}

            result = subprocess.run(
                ["bash", str(tier0_script)],
                capture_output=True, text=True, timeout=60,
                cwd=str(repo_root),
            )
            output = result.stdout + result.stderr
            # Parse pass/fail from output (typical format: "X passed" or "X/Y PASS")
            import re
            passed_match = re.search(r'(\d+)\s+passed', output)
            fail_match = re.search(r'(\d+)\s+failed', output)
            status = {
                "_source": str(tier0_script),
                "exit_code": result.returncode,
                "passed": passed_match.group(1) if passed_match else "?",
                "failed": fail_match.group(1) if fail_match else "0",
                "summary": output.strip()[-500:],  # last 500 chars
            }
            StateEncoder._tier0_module_cache = status
            StateEncoder._tier0_module_cache_at = now
            return status
        except subprocess.TimeoutExpired:
            status = {"_source": str(tier0_script), "status": "timeout",
                      "exit_code": 124, "summary": "tier0 timed out after 60s"}
            StateEncoder._tier0_module_cache = status
            StateEncoder._tier0_module_cache_at = now
            return status
        except Exception as e:
            return {"_source": "unknown", "status": "error",
                    "exit_code": -1, "summary": str(e)[:200]}

    # ── 查询接口 ──

    def get_dependents(self, file_path: str) -> List[str]:
        """查询：改了 file_path 会影响哪些文件"""
        state = self.encode()
        direct = state.reverse_call_graph.get(file_path, [])
        # 传递闭包：直接+间接调用者
        all_affected = set(direct)
        changed = True
        while changed:
            changed = False
            for f in list(all_affected):
                for caller in state.reverse_call_graph.get(f, []):
                    if caller not in all_affected:
                        all_affected.add(caller)
                        changed = True
        return sorted(all_affected)

    def get_fan_out(self, file_path: str) -> int:
        """文件被多少其他文件依赖"""
        state = self.encode()
        return len(state.reverse_call_graph.get(file_path, []))

    def get_constraint_violations(self, proposed_changes: List[str]) -> List[str]:
        """检查拟改文件是否违反约束"""
        state = self.encode()
        violations = []
        for fpath in proposed_changes:
            for constraint, protected_files in state.constraint_map.items():
                if fpath in protected_files:
                    violations.append(f"{fpath} is in constraint group '{constraint}'")
        return violations
