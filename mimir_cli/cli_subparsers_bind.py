"""Argparse subparser definitions — part 2 (P1-LONG-GOD)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mimir_cli.main_dispatch import get_command_handlers, _require_tty
from mimir_cli.paths import openclaw_migration_source_default

_OPENCLAW_MIGRATE_SOURCE_DEFAULT = str(openclaw_migration_source_default()).replace(
    str(Path.home()), "~", 1
)

logger = logging.getLogger(__name__)


def configure_parser_part2(parser, subparsers) -> None:
    """Register plugins through logs subcommands (second half)."""
    handlers = get_command_handlers()

    # =========================================================================
    # plugins command
    # =========================================================================
    plugins_parser = subparsers.add_parser(
        "plugins",
        help="Manage plugins — install, update, remove, list",
        description="Install plugins from Git repositories, update, remove, or list them.",
    )
    plugins_subparsers = plugins_parser.add_subparsers(dest="plugins_action")

    plugins_install = plugins_subparsers.add_parser(
        "install", help="Install a plugin from a Git URL or owner/repo"
    )
    plugins_install.add_argument(
        "identifier",
        help="Git URL or owner/repo shorthand (e.g. anpicasso/mimir-plugin-chrome-profiles)",
    )
    plugins_install.add_argument(
        "--force", "-f", action="store_true",
        help="Remove existing plugin and reinstall",
    )

    plugins_update = plugins_subparsers.add_parser(
        "update", help="Pull latest changes for an installed plugin"
    )
    plugins_update.add_argument("name", help="Plugin name to update")

    plugins_remove = plugins_subparsers.add_parser(
        "remove", aliases=["rm", "uninstall"], help="Remove an installed plugin"
    )
    plugins_remove.add_argument("name", help="Plugin directory name to remove")

    plugins_subparsers.add_parser("list", aliases=["ls"], help="List installed plugins")

    plugins_enable = plugins_subparsers.add_parser(
        "enable", help="Enable a disabled plugin"
    )
    plugins_enable.add_argument("name", help="Plugin name to enable")

    plugins_disable = plugins_subparsers.add_parser(
        "disable", help="Disable a plugin without removing it"
    )
    plugins_disable.add_argument("name", help="Plugin name to disable")

    def cmd_plugins(args):
        from mimir_cli.plugins_cmd import plugins_command
        plugins_command(args)

    plugins_parser.set_defaults(func=cmd_plugins)

    # =========================================================================
    # Plugin CLI commands — dynamically registered by memory/general plugins.
    # Plugins provide a register_cli(subparser) function that builds their
    # own argparse tree.  No hardcoded plugin commands in main.py.
    # =========================================================================
    try:
        from plugins.memory import discover_plugin_cli_commands
        for cmd_info in discover_plugin_cli_commands():
            plugin_parser = subparsers.add_parser(
                cmd_info["name"],
                help=cmd_info["help"],
                description=cmd_info.get("description", ""),
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter,
            )
            cmd_info["setup_fn"](plugin_parser)
    except Exception as _exc:
        import logging as _log
        _log.getLogger(__name__).debug("Plugin CLI discovery failed: %s", _exc)

    # =========================================================================
    # memory command
    # =========================================================================
    memory_parser = subparsers.add_parser(
        "memory",
        help="Configure external memory provider",
        description=(
            "Set up and manage external memory provider plugins.\n\n"
            "Available providers: honcho, openviking, mem0, hindsight,\n"
            "holographic, retaindb, byterover.\n\n"
            "Only one external provider can be active at a time.\n"
            "Built-in memory (MEMORY.md/USER.md) is always active."
        ),
    )
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    memory_sub.add_parser("setup", help="Interactive provider selection and configuration")
    memory_sub.add_parser("status", help="Show current memory provider config")
    memory_sub.add_parser("off", help="Disable external provider (built-in only)")

    def cmd_memory(args):
        sub = getattr(args, "memory_command", None)
        if sub == "off":
            from mimir_cli.config import load_config, save_config
            config = load_config()
            if not isinstance(config.get("memory"), dict):
                config["memory"] = {}
            config["memory"]["provider"] = ""
            save_config(config)
            print("\n  ✓ Memory provider: built-in only")
            print("  Saved to config.yaml\n")
        else:
            from mimir_cli.memory_setup import memory_command
            memory_command(args)

    memory_parser.set_defaults(func=cmd_memory)

    # =========================================================================
    # tools command
    # =========================================================================
    tools_parser = subparsers.add_parser(
        "tools",
        help="Configure which tools are enabled per platform",
        description=(
            "Enable, disable, or list tools for CLI, Telegram, Discord, etc.\n\n"
            "Built-in toolsets use plain names (e.g. web, memory).\n"
            "MCP tools use server:tool notation (e.g. github:create_issue).\n\n"
            "Run 'mimir tools' with no subcommand for the interactive configuration UI."
        ),
    )
    tools_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a summary of enabled tools per platform and exit"
    )
    tools_sub = tools_parser.add_subparsers(dest="tools_action")

    # mimir tools list [--platform cli]
    tools_list_p = tools_sub.add_parser(
        "list",
        help="Show all tools and their enabled/disabled status",
    )
    tools_list_p.add_argument(
        "--platform", default="cli",
        help="Platform to show (default: cli)",
    )

    # mimir tools disable <name...> [--platform cli]
    tools_disable_p = tools_sub.add_parser(
        "disable",
        help="Disable toolsets or MCP tools",
    )
    tools_disable_p.add_argument(
        "names", nargs="+", metavar="NAME",
        help="Toolset name (e.g. web) or MCP tool in server:tool form",
    )
    tools_disable_p.add_argument(
        "--platform", default="cli",
        help="Platform to apply to (default: cli)",
    )

    # mimir tools enable <name...> [--platform cli]
    tools_enable_p = tools_sub.add_parser(
        "enable",
        help="Enable toolsets or MCP tools",
    )
    tools_enable_p.add_argument(
        "names", nargs="+", metavar="NAME",
        help="Toolset name or MCP tool in server:tool form",
    )
    tools_enable_p.add_argument(
        "--platform", default="cli",
        help="Platform to apply to (default: cli)",
    )

    def cmd_tools(args):
        action = getattr(args, "tools_action", None)
        if action in ("list", "disable", "enable"):
            from mimir_cli.tools_config import tools_disable_enable_command
            tools_disable_enable_command(args)
        else:
            _require_tty("tools")
            from mimir_cli.tools_config import tools_command
            tools_command(args)

    tools_parser.set_defaults(func=cmd_tools)
    # =========================================================================
    # mcp command — manage MCP server connections
    # =========================================================================
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Manage MCP servers and run MimirAether as an MCP server",
        description=(
            "Manage MCP server connections and run MimirAether as an MCP server.\n\n"
            "MCP servers provide additional tools via the Model Context Protocol.\n"
            "Use 'mimir mcp add' to connect to a new server, or\n"
            "'mimir mcp serve' to expose MimirAether conversations over MCP."
        ),
    )
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_action")

    mcp_serve_p = mcp_sub.add_parser(
        "serve",
        help="Run MimirAether as an MCP server (expose conversations to other agents)",
    )
    mcp_serve_p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging on stderr",
    )

    mcp_add_p = mcp_sub.add_parser("add", help="Add an MCP server (discovery-first install)")
    mcp_add_p.add_argument("name", help="Server name (used as config key)")
    mcp_add_p.add_argument("--url", help="HTTP/SSE endpoint URL")
    mcp_add_p.add_argument("--command", help="Stdio command (e.g. npx)")
    mcp_add_p.add_argument("--args", nargs="*", default=[], help="Arguments for stdio command")
    mcp_add_p.add_argument("--auth", choices=["oauth", "header"], help="Auth method")
    mcp_add_p.add_argument("--preset", help="Known MCP preset name")
    mcp_add_p.add_argument("--env", nargs="*", default=[], help="Environment variables for stdio servers (KEY=VALUE)")

    mcp_rm_p = mcp_sub.add_parser("remove", aliases=["rm"], help="Remove an MCP server")
    mcp_rm_p.add_argument("name", help="Server name to remove")

    mcp_sub.add_parser("list", aliases=["ls"], help="List configured MCP servers")

    mcp_test_p = mcp_sub.add_parser("test", help="Test MCP server connection")
    mcp_test_p.add_argument("name", help="Server name to test")

    mcp_cfg_p = mcp_sub.add_parser("configure", aliases=["config"], help="Toggle tool selection")
    mcp_cfg_p.add_argument("name", help="Server name to configure")

    def cmd_mcp(args):
        from mimir_cli.mcp_config import mcp_command
        mcp_command(args)

    mcp_parser.set_defaults(func=cmd_mcp)

    # =========================================================================
    # sessions command
    # =========================================================================
    sessions_parser = subparsers.add_parser(
        "sessions",
        help="Manage session history (list, rename, export, prune, delete)",
        description="View and manage the SQLite session store"
    )
    sessions_subparsers = sessions_parser.add_subparsers(dest="sessions_action")

    sessions_list = sessions_subparsers.add_parser("list", help="List recent sessions")
    sessions_list.add_argument("--source", help="Filter by source (cli, telegram, discord, etc.)")
    sessions_list.add_argument("--limit", type=int, default=20, help="Max sessions to show")

    sessions_export = sessions_subparsers.add_parser("export", help="Export sessions to a JSONL file")
    sessions_export.add_argument("output", help="Output JSONL file path (use - for stdout)")
    sessions_export.add_argument("--source", help="Filter by source")
    sessions_export.add_argument("--session-id", help="Export a specific session")

    sessions_delete = sessions_subparsers.add_parser("delete", help="Delete a specific session")
    sessions_delete.add_argument("session_id", help="Session ID to delete")
    sessions_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    sessions_prune = sessions_subparsers.add_parser("prune", help="Delete old sessions")
    sessions_prune.add_argument("--older-than", type=int, default=90, help="Delete sessions older than N days (default: 90)")
    sessions_prune.add_argument("--source", help="Only prune sessions from this source")
    sessions_prune.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    sessions_subparsers.add_parser("stats", help="Show session store statistics")

    sessions_rename = sessions_subparsers.add_parser("rename", help="Set or change a session's title")
    sessions_rename.add_argument("session_id", help="Session ID to rename")
    sessions_rename.add_argument("title", nargs="+", help="New title for the session")

    sessions_browse = sessions_subparsers.add_parser(
        "browse",
        help="Interactive session picker — browse, search, and resume sessions",
    )
    sessions_browse.add_argument("--source", help="Filter by source (cli, telegram, discord, etc.)")
    sessions_browse.add_argument("--limit", type=int, default=50, help="Max sessions to load (default: 50)")

    def _confirm_prompt(prompt: str) -> bool:
        """Prompt for y/N confirmation, safe against non-TTY environments."""
        try:
            return input(prompt).strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def cmd_sessions(args):
        import json as _json
        try:
            from mimir_state import SessionDB
            db = SessionDB()
        except Exception as e:
            print(f"Error: Could not open session database: {e}")
            return

        action = args.sessions_action

        # Hide third-party tool sessions by default, but honour explicit --source
        _source = getattr(args, "source", None)
        _exclude = None if _source else ["tool"]

        if action == "list":
            sessions = db.list_sessions_rich(source=args.source, exclude_sources=_exclude, limit=args.limit)
            if not sessions:
                print("No sessions found.")
                return
            has_titles = any(s.get("title") for s in sessions)
            if has_titles:
                print(f"{'Title':<32} {'Preview':<40} {'Last Active':<13} {'ID'}")
                print("─" * 110)
            else:
                print(f"{'Preview':<50} {'Last Active':<13} {'Src':<6} {'ID'}")
                print("─" * 95)
            for s in sessions:
                last_active = _relative_time(s.get("last_active"))
                preview = s.get("preview", "")[:38] if has_titles else s.get("preview", "")[:48]
                if has_titles:
                    title = (s.get("title") or "—")[:30]
                    sid = s["id"]
                    print(f"{title:<32} {preview:<40} {last_active:<13} {sid}")
                else:
                    sid = s["id"]
                    print(f"{preview:<50} {last_active:<13} {s['source']:<6} {sid}")

        elif action == "export":
            if args.session_id:
                resolved_session_id = db.resolve_session_id(args.session_id)
                if not resolved_session_id:
                    print(f"Session '{args.session_id}' not found.")
                    return
                data = db.export_session(resolved_session_id)
                if not data:
                    print(f"Session '{args.session_id}' not found.")
                    return
                line = _json.dumps(data, ensure_ascii=False) + "\n"
                if args.output == "-":
                    import sys
                    sys.stdout.write(line)
                else:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(line)
                    print(f"Exported 1 session to {args.output}")
            else:
                sessions = db.export_all(source=args.source)
                if args.output == "-":
                    import sys
                    for s in sessions:
                        sys.stdout.write(_json.dumps(s, ensure_ascii=False) + "\n")
                else:
                    with open(args.output, "w", encoding="utf-8") as f:
                        for s in sessions:
                            f.write(_json.dumps(s, ensure_ascii=False) + "\n")
                    print(f"Exported {len(sessions)} sessions to {args.output}")

        elif action == "delete":
            resolved_session_id = db.resolve_session_id(args.session_id)
            if not resolved_session_id:
                print(f"Session '{args.session_id}' not found.")
                return
            if not args.yes:
                if not _confirm_prompt(f"Delete session '{resolved_session_id}' and all its messages? [y/N] "):
                    print("Cancelled.")
                    return
            if db.delete_session(resolved_session_id):
                print(f"Deleted session '{resolved_session_id}'.")
            else:
                print(f"Session '{args.session_id}' not found.")

        elif action == "prune":
            days = args.older_than
            source_msg = f" from '{args.source}'" if args.source else ""
            if not args.yes:
                if not _confirm_prompt(f"Delete all ended sessions older than {days} days{source_msg}? [y/N] "):
                    print("Cancelled.")
                    return
            count = db.prune_sessions(older_than_days=days, source=args.source)
            print(f"Pruned {count} session(s).")

        elif action == "rename":
            resolved_session_id = db.resolve_session_id(args.session_id)
            if not resolved_session_id:
                print(f"Session '{args.session_id}' not found.")
                return
            title = " ".join(args.title)
            try:
                if db.set_session_title(resolved_session_id, title):
                    print(f"Session '{resolved_session_id}' renamed to: {title}")
                else:
                    print(f"Session '{args.session_id}' not found.")
            except ValueError as e:
                print(f"Error: {e}")

        elif action == "browse":
            limit = getattr(args, "limit", 50) or 50
            source = getattr(args, "source", None)
            _browse_exclude = None if source else ["tool"]
            sessions = db.list_sessions_rich(source=source, exclude_sources=_browse_exclude, limit=limit)
            db.close()
            if not sessions:
                print("No sessions found.")
                return

            selected_id = _session_browse_picker(sessions)
            if not selected_id:
                print("Cancelled.")
                return

            # Launch mimir --resume <id> by replacing the current process
            print(f"Resuming session: {selected_id}")
            import shutil
            hermes_bin = shutil.which("mimir")
            if hermes_bin:
                os.execvp(hermes_bin, ["mimir", "--resume", selected_id])
            else:
                # Fallback: re-invoke via python -m
                os.execvp(
                    sys.executable,
                    [sys.executable, "-m", "mimir_cli.main", "--resume", selected_id],
                )
            return  # won't reach here after execvp

        elif action == "stats":
            total = db.session_count()
            msgs = db.message_count()
            print(f"Total sessions: {total}")
            print(f"Total messages: {msgs}")
            for src in ["cli", "telegram", "discord", "whatsapp", "slack"]:
                c = db.session_count(source=src)
                if c > 0:
                    print(f"  {src}: {c} sessions")
            db_path = db.db_path
            if db_path.exists():
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                print(f"Database size: {size_mb:.1f} MB")

        else:
            sessions_parser.print_help()

        db.close()

    sessions_parser.set_defaults(func=cmd_sessions)

    # =========================================================================
    # insights command
    # =========================================================================
    insights_parser = subparsers.add_parser(
        "insights",
        help="Show usage insights and analytics",
        description="Analyze session history to show token usage, costs, tool patterns, and activity trends"
    )
    insights_parser.add_argument("--days", type=int, default=30, help="Number of days to analyze (default: 30)")
    insights_parser.add_argument("--source", help="Filter by platform (cli, telegram, discord, etc.)")

    def cmd_insights(args):
        try:
            from mimir_state import SessionDB
            from agent.insights import InsightsEngine

            db = SessionDB()
            engine = InsightsEngine(db)
            report = engine.generate(days=args.days, source=args.source)
            print(engine.format_terminal(report))
            db.close()
        except Exception as e:
            print(f"Error generating insights: {e}")

    insights_parser.set_defaults(func=cmd_insights)

    # =========================================================================
    # claw command (OpenClaw migration)
    # =========================================================================
    claw_parser = subparsers.add_parser(
        "claw",
        help="OpenClaw migration tools",
        description="Migrate settings, memories, skills, and API keys from OpenClaw to MimirAether"
    )
    claw_subparsers = claw_parser.add_subparsers(dest="claw_action")

    # claw migrate
    claw_migrate = claw_subparsers.add_parser(
        "migrate",
        help="Migrate from OpenClaw to MimirAether",
        description="Import settings, memories, skills, and API keys from an OpenClaw installation. "
                    "Always shows a preview before making changes."
    )
    claw_migrate.add_argument(
        "--source",
        help=f"Path to OpenClaw directory (default: {_OPENCLAW_MIGRATE_SOURCE_DEFAULT})",
    )
    claw_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only — stop after showing what would be migrated"
    )
    claw_migrate.add_argument(
        "--preset",
        choices=["user-data", "full"],
        default="full",
        help="Migration preset (default: full). 'user-data' excludes secrets"
    )
    claw_migrate.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files (default: skip conflicts)"
    )
    claw_migrate.add_argument(
        "--migrate-secrets",
        action="store_true",
        help="Include allowlisted secrets (TELEGRAM_BOT_TOKEN, API keys, etc.)"
    )
    claw_migrate.add_argument(
        "--workspace-target",
        help="Absolute path to copy workspace instructions into"
    )
    claw_migrate.add_argument(
        "--skill-conflict",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help="How to handle skill name conflicts (default: skip)"
    )
    claw_migrate.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )

    # claw cleanup
    claw_cleanup = claw_subparsers.add_parser(
        "cleanup",
        aliases=["clean"],
        help="Archive leftover OpenClaw directories after migration",
        description="Scan for and archive leftover OpenClaw directories to prevent state fragmentation"
    )
    claw_cleanup.add_argument(
        "--source",
        help="Path to a specific OpenClaw directory to clean up"
    )
    claw_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be archived without making changes"
    )
    claw_cleanup.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )

    def cmd_claw(args):
        from mimir_cli.claw import claw_command
        claw_command(args)

    claw_parser.set_defaults(func=cmd_claw)

    # =========================================================================
    # version command
    # =========================================================================
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information"
    )
    version_parser.set_defaults(func=handlers['cmd_version'])

    # =========================================================================
    # update command
    # =========================================================================
    update_parser = subparsers.add_parser(
        "update",
        help="Update MimirAether to the latest version",
        description="Pull the latest changes from git and reinstall dependencies"
    )
    update_parser.add_argument(
        "--gateway", action="store_true", default=False,
        help="Gateway mode: use file-based IPC for prompts instead of stdin (used internally by /update)"
    )
    update_parser.set_defaults(func=handlers['cmd_update'])

    # =========================================================================
    # uninstall command
    # =========================================================================
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Uninstall MimirAether",
        description="Remove MimirAether from your system. Can keep configs/data for reinstall."
    )
    uninstall_parser.add_argument(
        "--full",
        action="store_true",
        help="Full uninstall - remove everything including configs and data"
    )
    uninstall_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )
    uninstall_parser.set_defaults(func=handlers['cmd_uninstall'])

    # =========================================================================
    # acp command
    # =========================================================================
    acp_parser = subparsers.add_parser(
        "acp",
        help="Run MimirAether as an ACP (Agent Client Protocol) server",
        description="Start MimirAether in ACP mode for editor integration (VS Code, Zed, JetBrains)",
    )

    def cmd_acp(args):
        """Launch MimirAether as an ACP server."""
        try:
            from acp_adapter.entry import main as acp_main
            acp_main()
        except ImportError:
            print("ACP dependencies not installed.")
            print("Install them with:  pip install -e '.[acp]'")
            sys.exit(1)

    acp_parser.set_defaults(func=cmd_acp)

    # =========================================================================
    # profile command
    # =========================================================================
    profile_parser = subparsers.add_parser(
        "profile",
        help="Manage profiles — multiple isolated MimirAether instances",
    )
    profile_subparsers = profile_parser.add_subparsers(dest="profile_action")

    profile_subparsers.add_parser("list", help="List all profiles")
    profile_use = profile_subparsers.add_parser("use", help="Set sticky default profile")
    profile_use.add_argument("profile_name", help="Profile name (or 'default')")

    profile_create = profile_subparsers.add_parser("create", help="Create a new profile")
    profile_create.add_argument("profile_name", help="Profile name (lowercase, alphanumeric)")
    profile_create.add_argument("--clone", action="store_true",
                                help="Copy config.yaml, .env, SOUL.md from active profile")
    profile_create.add_argument("--clone-all", action="store_true",
                                help="Full copy of active profile (all state)")
    profile_create.add_argument("--clone-from", metavar="SOURCE",
                                help="Source profile to clone from (default: active)")
    profile_create.add_argument("--no-alias", action="store_true",
                                help="Skip wrapper script creation")

    profile_delete = profile_subparsers.add_parser("delete", help="Delete a profile")
    profile_delete.add_argument("profile_name", help="Profile to delete")
    profile_delete.add_argument("-y", "--yes", action="store_true",
                                help="Skip confirmation prompt")

    profile_show = profile_subparsers.add_parser("show", help="Show profile details")
    profile_show.add_argument("profile_name", help="Profile to show")

    profile_alias = profile_subparsers.add_parser("alias", help="Manage wrapper scripts")
    profile_alias.add_argument("profile_name", help="Profile name")
    profile_alias.add_argument("--remove", action="store_true",
                               help="Remove the wrapper script")
    profile_alias.add_argument("--name", dest="alias_name", metavar="NAME",
                               help="Custom alias name (default: profile name)")

    profile_rename = profile_subparsers.add_parser("rename", help="Rename a profile")
    profile_rename.add_argument("old_name", help="Current profile name")
    profile_rename.add_argument("new_name", help="New profile name")

    profile_export = profile_subparsers.add_parser("export", help="Export a profile to archive")
    profile_export.add_argument("profile_name", help="Profile to export")
    profile_export.add_argument("-o", "--output", default=None,
                                help="Output file (default: <name>.tar.gz)")

    profile_import = profile_subparsers.add_parser("import", help="Import a profile from archive")
    profile_import.add_argument("archive", help="Path to .tar.gz archive")
    profile_import.add_argument("--name", dest="import_name", metavar="NAME",
                                help="Profile name (default: inferred from archive)")

    profile_parser.set_defaults(func=handlers['cmd_profile'])

    # =========================================================================
    # completion command
    # =========================================================================
    completion_parser = subparsers.add_parser(
        "completion",
        help="Print shell completion script (bash or zsh)",
    )
    completion_parser.add_argument(
        "shell", nargs="?", default="bash", choices=["bash", "zsh"],
        help="Shell type (default: bash)",
    )
    completion_parser.set_defaults(func=handlers['cmd_completion'])

    # =========================================================================
    # dashboard command
    # =========================================================================
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start the web UI dashboard",
        description="Launch the MimirAether web dashboard for managing config, API keys, and sessions",
    )
    dashboard_parser.add_argument("--port", type=int, default=9119, help="Port (default 9119)")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Host (default 127.0.0.1)")
    dashboard_parser.add_argument("--no-open", action="store_true", help="Don't open browser automatically")
    dashboard_parser.set_defaults(func=handlers['cmd_dashboard'])

    # =========================================================================
    # logs command
    # =========================================================================
    logs_parser = subparsers.add_parser(
        "logs",
        help="View and filter MimirAether log files",
        description="View, tail, and filter agent.log / errors.log / gateway.log",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
    Examples:
    mimir logs                    Show last 50 lines of agent.log
    mimir logs -f                 Follow agent.log in real time
    mimir logs errors             Show last 50 lines of errors.log
    mimir logs gateway -n 100     Show last 100 lines of gateway.log
    mimir logs --level WARNING    Only show WARNING and above
    mimir logs --session abc123   Filter by session ID
    mimir logs --component tools  Only show tool-related lines
    mimir logs --since 1h         Lines from the last hour
    mimir logs --since 30m -f     Follow, starting from 30 min ago
    mimir logs list               List available log files with sizes
    """,
    )
    logs_parser.add_argument(
        "log_name", nargs="?", default="agent",
        help="Log to view: agent (default), errors, gateway, or 'list' to show available files",
    )
    logs_parser.add_argument(
        "-n", "--lines", type=int, default=50,
        help="Number of lines to show (default: 50)",
    )
    logs_parser.add_argument(
        "-f", "--follow", action="store_true",
        help="Follow the log in real time (like tail -f)",
    )
    logs_parser.add_argument(
        "--level", metavar="LEVEL",
        help="Minimum log level to show (DEBUG, INFO, WARNING, ERROR)",
    )
    logs_parser.add_argument(
        "--session", metavar="ID",
        help="Filter lines containing this session ID substring",
    )
    logs_parser.add_argument(
        "--since", metavar="TIME",
        help="Show lines since TIME ago (e.g. 1h, 30m, 2d)",
    )
    logs_parser.add_argument(
        "--component", metavar="NAME",
        help="Filter by component: gateway, agent, tools, cli, cron",
    )
    logs_parser.set_defaults(func=handlers['cmd_logs'])

    # =========================================================================