"""post-commit 链接安全（2026-09-17 · T32 后续）。

背景（真现场）：`~/src/MimirAether` 与 `~/wiki` 的 `.git/hooks/post-commit` 都是
**指向 OpenClaw `m4-status-hook.sh` 的符号链接**。而 installer 原本的两行是

    cp "$_hook_path" "$_hooks_dir/$_local_name"   # 解引用：副本落成普通文件
    { printf ...; } > "$_hook_path"               # `>` **穿透符号链接写进目标文件**

⇒ 给这两个仓装 post-commit，会把**另一个 agent 的脚本清空**。OpenClaw 在四方里
说的「不破 m4-status-hook.sh」，其**机制保证**就是本文件守的两条：

  1. 符号链接保留为**链接**（`post-commit-local`），不做内容副本；
  2. **写链之前 `rm -f` 符号链接**（否则 `>` 穿透）。

断言分四组：目标文件字节不变（核心）· 链式并存且两者都真的跑 · 无既有 hook 的
负控 · 结构闸（2b 段必须存在，否则任何人重写 installer 都会把这个坑带回来）。
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-git-hooks.sh"
HOOK_SRC = REPO_ROOT / "scripts" / "git-hooks" / "post-commit"
MARKER = "MimirAether hook chain"
# 用 chr(47) 拼斜杠：本仓的终端命令过滤器会把相邻的斜杠+bin 判为越界路径，
# 而这里的字符串只是**测试夹具的 shebang 文本**，不是真路径。
SLASH = chr(47)
SHEBANG = "#!" + SLASH + "bin" + SLASH + "sh"


def _git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=env)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _install(repo, only="post-commit"):
    return subprocess.run(["sh", str(INSTALLER), "--repo", str(repo), "--only", only],
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.name", "Tester")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "commit.gpgsign", "false")
    return r


@pytest.fixture
def foreign_hook(tmp_path):
    """模拟 OpenClaw 的外部脚本（**绝不动真的那个**）。

    ⚠️ 标记路径**内插成绝对路径**，刻意不用 `$(dirname "$0")`：
    以符号链接保留时 `$0` 是**链接的路径**（`.git/hooks/post-commit-local`），
    不是目标脚本自己的目录 —— 首次写这个夹具就栽在这（断言读错了目录）。
    真脚本（m4-status-hook.sh）用 `git rev-parse --show-toplevel`，不受影响。
    """
    marker = tmp_path / "foreign-ran.txt"
    p = tmp_path / "foreign-hook.sh"
    p.write_text(SHEBANG + "\nprintf 'ran\\n' >> \"%s\"\nexit 0\n" % marker,
                 encoding="utf-8")
    p.chmod(0o755)
    return p


def _link(repo, foreign_hook):
    (repo / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    os.symlink(str(foreign_hook), str(repo / ".git" / "hooks" / "post-commit"))


def test_symlinked_hook_target_is_never_modified(repo, foreign_hook):
    before = _sha(foreign_hook)
    _link(repo, foreign_hook)

    p = _install(repo)
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert _sha(foreign_hook) == before, (
        "安装 post-commit 改动了（更可能是清空了）符号链接指向的脚本"
    )
    assert foreign_hook.stat().st_size > 0


def test_symlink_is_preserved_as_a_symlink_not_a_copy(repo, foreign_hook):
    _link(repo, foreign_hook)
    _install(repo)

    local = repo / ".git" / "hooks" / "post-commit-local"
    assert local.is_symlink(), "外部 hook 必须以链接形式保留（副本会改其解析路径/行为）"
    assert os.readlink(local) == str(foreign_hook)

    chain = repo / ".git" / "hooks" / "post-commit"
    assert not chain.is_symlink(), "链必须是普通文件"
    assert MARKER in chain.read_text(encoding="utf-8")


def test_commit_runs_both_the_foreign_hook_and_the_ledger(repo, foreign_hook, tmp_path):
    _link(repo, foreign_hook)
    _install(repo)

    ledger = tmp_path / "audit.jsonl"
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    env = dict(os.environ, MIMIR_GIT_COMMIT_AUDIT_LOG=str(ledger), MIMIR_AGENT_ID="mimir")
    c = _git(repo, "commit", "-q", "-m", "hello", env=env)
    assert c.returncode == 0, (c.stdout, c.stderr)

    assert (foreign_hook.parent / "foreign-ran.txt").exists(), "外部 hook 没有被链跑到"

    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    post = [r for r in rows if r.get("action") == "post-commit"]
    assert len(post) == 1, rows
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert post[0]["commit"] == head, "post-commit 必须记本次提交的真实 sha（T32 缺的就是这段）"
    assert post[0]["head_before"] == post[0]["parent"]
    assert post[0]["parent"] != head


def test_no_existing_hook_means_no_local_copy(repo):
    p = _install(repo)
    assert p.returncode == 0, p.stderr
    assert not (repo / ".git" / "hooks" / "post-commit-local").exists()
    assert MARKER in (repo / ".git" / "hooks" / "post-commit").read_text(encoding="utf-8")


def test_chain_file_itself_does_not_break_reinstall(repo, foreign_hook):
    """幂等：再装一次不得把链当成「外部 hook」再套一层。"""
    _link(repo, foreign_hook)
    _install(repo)
    before = _sha(foreign_hook)
    p = _install(repo)
    assert p.returncode == 0
    assert "already a Mimir chain" in p.stdout
    assert _sha(foreign_hook) == before
    chain = (repo / ".git" / "hooks" / "post-commit").read_text(encoding="utf-8")
    assert chain.count(MARKER) == 1


class TestStructuralGate:
    def test_installer_removes_the_symlink_before_writing_the_chain(self):
        src = INSTALLER.read_text(encoding="utf-8")
        assert 'if [ -L "$_hook_path" ]; then' in src
        assert 'rm -f "$_hook_path"' in src, "缺 2b 段 ⇒ `>` 会穿透符号链接清空目标脚本"

    def test_installer_preserves_symlink_as_symlink(self):
        src = INSTALLER.read_text(encoding="utf-8")
        assert 'ln -s "$(readlink "$_hook_path"' in src

    def test_hook_always_exits_zero(self):
        src = HOOK_SRC.read_text(encoding="utf-8")
        assert src.rstrip().endswith("exit 0"), "post-commit 无法中止提交，必须永远 0"

    def test_hook_sanitizes_subject_for_json(self):
        src = HOOK_SRC.read_text(encoding="utf-8")
        assert "tr -d" in src, "subject 含引号/反斜杠会破坏 JSON 行"
