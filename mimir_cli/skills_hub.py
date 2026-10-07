"""
Skills CLI - the ported surface of the Hermes Skills Hub command.

Powers both:
  - `mimir skills <subcommand>` (CLI argparse entry point)
  - `/skills <subcommand>` (slash command in the interactive chat)

Ported: `list` (installed skills) + the `config` route (mimir_cli/skills_config).

NOT ported: the hub subsystem - browse / search / install / inspect / check /
update / audit / uninstall / publish / snapshot / tap. `tools.skills_hub` here is
a state layer only (HubLockFile / ensure_hub_dirs), so those verbs are deprecated:
each prints an error naming the fix and exits EXIT_UNSUPPORTED, never a traceback.
They are flagged DEPRECATED in `mimir skills --help`.

Exit-code contract:
  0 success | 2 usage error | 3 subcommand not available in this build
  4 reserved for runtime failure | 130 interrupt
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Lazy imports to avoid circular dependencies and slow startup.
# tools.skills_hub and tools.skills_guard are imported inside functions.

_console = Console()


# ---------------------------------------------------------------------------
# Shared do_* functions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Deprecation surface: exit-code contract + the deprecated-verb table
# ---------------------------------------------------------------------------

# Exit-code contract (L32: distinct codes for distinct failure classes)
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3
EXIT_RUNTIME = 4
EXIT_INTERRUPT = 130

# Deprecated subcommand -> (upstream module that owns it, replacement here)
_DEPRECATED_SUBCOMMANDS = {
    "search": ("tools.skills_hub_search", "mimir skills list --source local"),
    "browse": ("tools.skills_hub_search", "mimir skills list --source all"),
    "inspect": ("tools.skills_hub_search", "mimir skills list --source local"),
    "install": ("tools.skills_hub_install", "copy the skill into skills/ by hand"),
    "uninstall": ("tools.skills_hub_install", "delete its directory under skills/"),
    "check": ("tools.skills_hub_install", "mimir skills list --source hub"),
    "update": ("tools.skills_hub_install", "re-copy the skill into skills/"),
    "audit": ("tools.skills_hub_install", "the skill audit scripts under scripts/"),
    "publish": ("tools.skills_hub_install", "open a PR against the target repository"),
    "snapshot": ("tools.skills_hub_install", "mimir backup"),
    "tap": ("tools.skills_hub", "nothing to configure: skills are read from skills/"),
}

_DEPRECATED_HEADER = "ERROR: 'mimir skills {sub}' is not available in MimirAether."


def _emit_deprecated(sub: str, console=None) -> int:
    """Print an actionable deprecation notice and return the exit code."""
    import sys

    mod, alt = _DEPRECATED_SUBCOMMANDS.get(sub, ("tools.skills_hub", "mimir skills list"))
    lines = [
        _DEPRECATED_HEADER.format(sub=sub),
        "  Cause: the hub subsystem was never ported. 'tools.skills_hub' in this",
        "         repository is a state layer only (HubLockFile / ensure_hub_dirs);",
        "         the module that owns " + sub + " (" + mod + ") does not exist here.",
        "  Fix:   use '" + alt + "'",
        "         or run 'mimir skills list' to see what is actually installed.",
        "  Note:  deprecated on purpose, not broken by accident; it is flagged",
        "         DEPRECATED in --help and will be removed in a future release.",
    ]
    text = "\n".join(lines)
    if console is None:
        sys.stderr.write(text + "\n")
    else:
        try:
            console.print(text)
        except Exception:
            sys.stderr.write(text + "\n")
    return EXIT_UNSUPPORTED


def do_list(source_filter: str = "all", console: Optional[Console] = None) -> None:
    """List installed skills, distinguishing hub, builtin, and local skills."""
    from skills.skills_loader import SKILLS_DIR, _scan_dir_for_skills, skills_list
    from tools.skills_hub import HubLockFile, ensure_hub_dirs

    c = console or _console
    ensure_hub_dirs()
    lock = HubLockFile()
    hub_installed = {e["name"]: e for e in lock.list_installed()}

    # 内置名单真源 = 仓内 skills/（get_skills_source_dir docstring:「MimirAether内置」）。
    # 必须逐 SKILL.md 扫出**技能名**；SkillSync.list_skills() 返回的是**分类名**
    # （data/feeds/github/...），拿它当 builtin 判据会恒 0 —— 已实测排除。
    builtin_names = {s["name"] for s in _scan_dir_for_skills(SKILLS_DIR)}

    # 全量技能真源 = 仓内 skills/ + 用户侧 ~/.mimiraether/skills（合并去重，repo 侧优先）
    all_skills = skills_list()

    table = Table(title="Installed Skills")
    table.add_column("Name", style="bold cyan")
    table.add_column("Category", style="dim")
    table.add_column("Source", style="dim")
    table.add_column("Trust", style="dim")

    hub_count = 0
    builtin_count = 0
    local_count = 0

    for skill in sorted(all_skills, key=lambda s: (s.get("category") or "", s["name"])):
        name = skill["name"]
        category = skill.get("category", "")
        hub_entry = hub_installed.get(name)

        if hub_entry:
            source_type = "hub"
            source_display = hub_entry.get("source", "hub")
            trust = hub_entry.get("trust_level", "community")
            hub_count += 1
        elif name in builtin_names:
            source_type = "builtin"
            source_display = "builtin"
            trust = "builtin"
            builtin_count += 1
        else:
            source_type = "local"
            source_display = "local"
            trust = "local"
            local_count += 1

        if source_filter != "all" and source_filter != source_type:
            continue

        trust_style = {"builtin": "bright_cyan", "trusted": "green", "community": "yellow", "local": "dim"}.get(trust, "dim")
        trust_label = "official" if source_display == "official" else trust
        table.add_row(name, category, source_display, f"[{trust_style}]{trust_label}[/]")

    c.print(table)
    c.print(
        f"[dim]{hub_count} hub-installed, {builtin_count} builtin, {local_count} local[/]\n"
    )


# ---------------------------------------------------------------------------
# CLI argparse entry point
# ---------------------------------------------------------------------------

def skills_command(args) -> int:
    """Router for `mimir skills <subcommand>` - called from mimir_cli/main.py.

    Only `list` is functional in MimirAether: the hub subsystem (search / install /
    taps / audit / snapshot / publish) was never ported - `tools.skills_hub` here is
    a state layer only. Deprecated subcommands return EXIT_UNSUPPORTED with a fix,
    never a traceback (Developer Tooling Engineer L30/L32/L35).
    """
    action = getattr(args, "skills_action", None)

    if action == "list":
        do_list(source_filter=args.source)
        return EXIT_OK

    if action in _DEPRECATED_SUBCOMMANDS:
        return _emit_deprecated(action, console=_console)

    _console.print("Usage: mimir skills [list]\n")
    _console.print("Hub subcommands (search/install/tap/...) are deprecated - "
                    "run 'mimir skills search' to see why and what to use instead.\n")
    return EXIT_USAGE


# ---------------------------------------------------------------------------
# Slash command entry point (/skills in chat)
# ---------------------------------------------------------------------------

def handle_skills_slash(cmd: str, console: Optional[Console] = None) -> None:
    """Parse and dispatch `/skills <subcommand> [args]` from the chat interface.

    Only `list` is functional in MimirAether - the hub subsystem was never ported.
    Deprecated verbs print a fix and return; they never raise (see skills_command).
    """
    c = console or _console
    parts = cmd.strip().split()

    # Strip the leading "/skills" if present
    if parts and parts[0].lower() == "/skills":
        parts = parts[1:]

    if not parts:
        _print_skills_help(c)
        return

    action = parts[0].lower()

    if action in _DEPRECATED_SUBCOMMANDS:
        _emit_deprecated(action, console=c)
        return

    if action == "list":
        source_filter = "all"
        rest = parts[1:]
        if "--source" in rest:
            idx = rest.index("--source")
            if idx + 1 < len(rest):
                source_filter = rest[idx + 1]
        do_list(source_filter=source_filter, console=c)
        return

    if action in ("help", "--help", "-h"):
        _print_skills_help(c)
        return

    c.print(f"[bold red]Unknown action:[/] {action}")
    _print_skills_help(c)


def _print_skills_help(console: Console) -> None:
    """Print help for the /skills slash command."""
    console.print(Panel(
        "[bold]Skills Commands (MimirAether):[/]\n\n"
        "  [cyan]list[/] [--source all|hub|builtin|local]  List installed skills\n"
        "  [cyan]config[/]                     Interactive enable/disable\n\n"
        "[bold]Deprecated (hub subsystem not ported):[/]\n"
        "  browse, search, install, inspect, check, update, audit,\n"
        "  uninstall, publish, snapshot, tap\n"
        "  These print a fix and exit 3 - they never raise a traceback.\n",
        title="/skills",
    ))
