#!/usr/bin/env python3
"""
MimirAether CLI - Main entry point.

Adapted from Hermes hermes_cli/main.py for MimirAether.

Usage:
    mimiraether                     # Interactive chat (default)
    mimiraether chat                # Interactive chat
    mimiraether status              # Show status
    mimiraether setup               # Interactive setup wizard
    mimiraether model               # Model selection
    mimiraether doctor              # Check configuration
    mimiraether sessions            # Session management
    mimiraether insights            # Usage insights
    mimiraether version             # Show version
    mimiraether mcp serve           # Start MCP server
"""

import argparse
import os
import subprocess
import sys
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from mimiraether_constants import get_mimiraether_home


def _relative_time(ts) -> str:
    """Format a timestamp as relative time (e.g., '2h ago', 'yesterday')."""
    if not ts:
        return "?"
    delta = _time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    if delta < 172800:
        return "yesterday"
    if delta < 604800:
        return f"{int(delta / 86400)}d ago"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _resolve_last_cli_session() -> Optional[str]:
    """Look up the most recent CLI session ID from SQLite. Returns None if unavailable."""
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        sessions = db.search_sessions(source="cli", limit=1)
        db.close()
        if sessions:
            return sessions[0]["id"]
    except Exception:
        pass
    return None


def _resolve_session_by_name_or_id(name_or_id: str) -> Optional[str]:
    """Resolve a session name (title) or ID to a session ID."""
    try:
        from hermes_state import SessionDB
        db = SessionDB()

        session = db.get_session(name_or_id)
        if session:
            db.close()
            return session["id"]

        session_id = db.resolve_session_by_title(name_or_id)
        db.close()
        return session_id
    except Exception:
        pass
    return None


def cmd_chat(args):
    """Run interactive chat CLI."""
    from cli import main as cli_main

    continue_val = getattr(args, "continue_last", None)
    if continue_val and not getattr(args, "resume", None):
        if isinstance(continue_val, str):
            resolved = _resolve_session_by_name_or_id(continue_val)
            if resolved:
                args.resume = resolved
            else:
                print(f"No session found matching '{continue_val}'.")
                sys.exit(1)
        else:
            last_id = _resolve_last_cli_session()
            if last_id:
                args.resume = last_id
            else:
                print("No previous CLI session found to continue.")
                sys.exit(1)

    resume_val = getattr(args, "resume", None)
    if resume_val:
        resolved = _resolve_session_by_name_or_id(resume_val)
        if resolved:
            args.resume = resolved

    kwargs = {
        "model": getattr(args, "model", None),
        "provider": getattr(args, "provider", None),
        "toolsets": getattr(args, "toolsets", None),
        "skills": getattr(args, "skills", None),
        "verbose": getattr(args, "verbose", False),
        "query": getattr(args, "query", None),
        "image": getattr(args, "image", None),
        "resume": getattr(args, "resume", None),
        "max_turns": getattr(args, "max_turns", None),
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        cli_main(**kwargs)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_status(args):
    """Show status of MimirAether components."""
    from hermes_state import SessionDB

    print()
    print("  MimirAether Status")
    print("  " + "=" * 50)

    db = SessionDB()
    total_sessions = db.session_count()
    cli_sessions = db.session_count(source="cli")
    total_messages = db.message_count()

    print(f"  Total sessions:  {total_sessions}")
    print(f"  CLI sessions:    {cli_sessions}")
    print(f"  Total messages:  {total_messages}")

    home = get_mimiraether_home()
    print(f"  Home directory: {home}")

    if home.exists():
        db_path = home / "state.db"
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            print(f"  Database size:   {size_kb:.1f} KB")

    db.close()
    print()


def cmd_sessions(args):
    """List and manage sessions."""
    from hermes_state import SessionDB

    db = SessionDB()
    limit = getattr(args, "limit", 20)
    sessions = db.list_sessions_rich(source=getattr(args, "source", None), limit=limit)
    db.close()

    if not sessions:
        print("  No sessions found.")
        return

    print()
    print(f"  Recent Sessions (showing {len(sessions)} of {limit})")
    print("  " + "-" * 60)
    for s in sessions:
        title = (s.get("title") or "").strip() or s["id"][:20]
        preview = (s.get("preview") or "").strip()
        last_active = _relative_time(s.get("last_active"))
        print(f"  {title}")
        if preview:
            print(f"    → {preview[:60]}")
        print(f"    {last_active} · {s.get('source', '?')} · {s.get('message_count', 0)} msgs")
        print()


def cmd_insights(args):
    """Generate usage insights report."""
    from agent.insights import InsightsEngine

    days = getattr(args, "days", 30)
    source = getattr(args, "source", None)

    try:
        from hermes_state import SessionDB
        db = SessionDB()
        engine = InsightsEngine(db)
        report = engine.generate(days=days, source=source)
        db.close()

        output_format = getattr(args, "format", "terminal")
        if output_format == "terminal":
            print(engine.format_terminal(report))
        else:
            print(engine.format_gateway(report))
    except Exception as e:
        print(f"Error generating insights: {e}")
        sys.exit(1)


def cmd_doctor(args):
    """Check configuration and dependencies."""
    print()
    print("  MimirAether Doctor")
    print("  " + "=" * 50)

    checks_passed = 0
    checks_failed = 0

    home = get_mimiraether_home()
    print(f"\n  Home directory: {home}")
    if home.exists():
        print("    ✓ Home directory exists")
        checks_passed += 1
    else:
        print("    ✗ Home directory does not exist")
        checks_failed += 1

    db_path = home / "state.db"
    print(f"\n  Database: {db_path}")
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"    ✓ Database exists ({size_kb:.1f} KB)")
        checks_passed += 1
    else:
        print("    ✗ Database does not exist yet (normal on first run)")
        checks_failed += 1

    print(f"\n  Python version: {sys.version.split()[0]}")

    print(f"\n  Results: {checks_passed} passed, {checks_failed} failed")
    print()


def cmd_version(args):
    """Show version information."""
    from mimiraether_constants import __version__ as mimiraether_version

    print()
    print("  MimirAether CLI")
    print(f"  Version: {mimiraether_version}")
    print(f"  Python:  {sys.version.split()[0]}")
    print()


def cmd_mcp(args):
    """MCP server management."""
    if getattr(args, "mcp_action", None) == "serve":
        from mcp_serve import run_mcp_server
        verbose = getattr(args, "verbose", False)
        run_mcp_server(verbose=verbose)
    else:
        print("  Use 'mimiraether mcp serve' to start the MCP server")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mimiraether",
        description="MimirAether - Intelligent AI Assistant",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    chat_parser = subparsers.add_parser("chat", help="Interactive chat")
    chat_parser.add_argument("-m", "--model", help="Model to use")
    chat_parser.add_argument("-p", "--provider", help="Provider to use")
    chat_parser.add_argument("-q", "--query", help="Single query to run")
    chat_parser.add_argument("-i", "--image", help="Image file path")
    chat_parser.add_argument("-r", "--resume", help="Resume session by ID or title")
    chat_parser.add_argument("-c", "--continue-last", nargs="?", const=True, help="Continue last session")
    chat_parser.add_argument("--max-turns", type=int, help="Max conversation turns")
    chat_parser.add_argument("--source", help="Session source tag")
    chat_parser.set_defaults(func=cmd_chat)

    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.set_defaults(func=cmd_status)

    sessions_parser = subparsers.add_parser("sessions", help="Manage sessions")
    sessions_parser.add_argument("--source", help="Filter by source")
    sessions_parser.add_argument("--limit", type=int, default=20, help="Max sessions to show")
    sessions_parser.set_defaults(func=cmd_sessions)

    insights_parser = subparsers.add_parser("insights", help="Generate usage insights")
    insights_parser.add_argument("--days", type=int, default=30, help="Days to look back")
    insights_parser.add_argument("--source", help="Filter by source")
    insights_parser.add_argument("--format", choices=["terminal", "gateway"], default="terminal", help="Output format")
    insights_parser.set_defaults(func=cmd_insights)

    doctor_parser = subparsers.add_parser("doctor", help="Check configuration")
    doctor_parser.set_defaults(func=cmd_doctor)

    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=cmd_version)

    mcp_parser = subparsers.add_parser("mcp", help="MCP server commands")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_action", help="MCP actions")
    mcp_serve_parser = mcp_subparsers.add_parser("serve", help="Start MCP server")
    mcp_serve_parser.add_argument("--verbose", action="store_true", help="Verbose output")
    mcp_serve_parser.set_defaults(func=cmd_mcp)

    setup_parser = subparsers.add_parser("setup", help="Interactive setup wizard")
    setup_parser.set_defaults(func=cmd_setup)

    model_parser = subparsers.add_parser("model", help="Model selection")
    model_parser.set_defaults(func=cmd_model)

    gateway_parser = subparsers.add_parser("gateway", help="Gateway management")
    gateway_subparsers = gateway_parser.add_subparsers(dest="gateway_action", help="Gateway actions")
    gateway_start = gateway_subparsers.add_parser("start", help="Start gateway")
    gateway_start.set_defaults(func=cmd_gateway)
    gateway_stop = gateway_subparsers.add_parser("stop", help="Stop gateway")
    gateway_stop.set_defaults(func=cmd_gateway)
    gateway_status = gateway_subparsers.add_parser("status", help="Show gateway status")
    gateway_status.set_defaults(func=cmd_gateway)
    gateway_parser.set_defaults(func=cmd_gateway)

    cron_parser = subparsers.add_parser("cron", help="Cron job management")
    cron_subparsers = cron_parser.add_subparsers(dest="cron_action", help="Cron actions")
    cron_list = cron_subparsers.add_parser("list", help="List cron jobs")
    cron_list.set_defaults(func=cmd_cron)
    cron_status = cron_subparsers.add_parser("status", help="Check cron status")
    cron_status.set_defaults(func=cmd_cron)
    cron_parser.set_defaults(func=cmd_cron)

    logs_parser = subparsers.add_parser("logs", help="View logs")
    logs_parser.add_argument("--lines", type=int, default=50, help="Number of lines")
    logs_parser.add_argument("--errors", action="store_true", help="Show errors only")
    logs_parser.set_defaults(func=cmd_logs)

    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if args.command is None:
        cmd_chat(args)
    else:
        func = getattr(args, "func", None)
        if func:
            func(args)
        else:
            parser.print_help()

# Additional CLI commands (from Hermes hermes_cli/main.py adaptation)
# =============================================================================

def cmd_setup(args):
    """Interactive setup wizard."""
    print()
    print("  MimirAether Setup Wizard")
    print("  " + "=" * 50)
    print()
    print("  This wizard will help you configure MimirAether.")
    print()

    # Check for existing .env
    env_file = get_mimiraether_home() / ".env"
    if env_file.exists():
        print(f"  Found existing .env at {env_file}")
        try:
            reply = input("  Overwrite? [y/N] ").strip().lower()
            if reply not in ("y", "yes"):
                print("  Setup cancelled.")
                return
        except (EOFError, KeyboardInterrupt):
            print()
            return

    # Model selection
    print()
    print("  Select your preferred model:")
    print("  1. MiniMax (default - fast, low cost)")
    print("  2. OpenAI GPT-4")
    print("  3. Anthropic Claude")
    print("  4. Custom model")
    try:
        choice = input("\n  Enter choice [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    model_choice = choice or "1"
    if model_choice == "1":
        model = "MiniMax/M2.7-highspeed"
        provider = "minimax"
    elif model_choice == "2":
        model = "gpt-4o"
        provider = "openai"
    elif model_choice == "3":
        model = "claude-sonnet-4-20250514"
        provider = "anthropic"
    else:
        model = input("  Enter model name: ").strip()
        provider = "custom"

    # API key collection
    api_key = ""
    if provider != "minimax":
        try:
            api_key = input(f"  Enter API key for {provider}: ").strip()
        except (EOFError, KeyboardInterrupt):
            api_key = ""

    # Write .env
    env_content = f"""# MimirAether Configuration
# Generated by setup wizard

# Model configuration
MIMIRAETHER_MODEL={model}
MIMIRAETHER_PROVIDER={provider}

"""
    if api_key:
        if provider == "openai":
            env_content += f"OPENAI_API_KEY={api_key}\n"
        elif provider == "anthropic":
            env_content += f"ANTHROPIC_API_KEY={api_key}\n"

    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(env_content)

    print()
    print(f"  Configuration saved to {env_file}")
    print()
    print("  Setup complete! Run 'mimiraether chat' to start.")
    print()


def cmd_model(args):
    """Model selection and configuration."""
    from mimiraether_constants import get_mimiraether_home

    print()
    print("  MimirAether Model Selection")
    print("  " + "=" * 50)
    print()

    # Load current config
    env_file = get_mimiraether_home() / ".env"
    current_model = "MiniMax/M2.7-highspeed"
    current_provider = "minimax"

    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("MIMIRAETHER_MODEL="):
                current_model = line.split("=", 1)[1].strip()
            elif line.startswith("MIMIRAETHER_PROVIDER="):
                current_provider = line.split("=", 1)[1].strip()

    print(f"  Current model: {current_model}")
    print(f"  Current provider: {current_provider}")
    print()
    print("  Available models:")
    print("  1. MiniMax/M2.7-highspeed (default)")
    print("  2. MiniMax/M2.7-flash (faster, cheaper)")
    print("  3. OpenAI GPT-4o")
    print("  4. Anthropic Claude Sonnet")
    print("  5. Custom model")
    print()
    try:
        choice = input("  Select model [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    model_choice = choice or "1"
    if model_choice == "1":
        new_model = "MiniMax/M2.7-highspeed"
        new_provider = "minimax"
    elif model_choice == "2":
        new_model = "MiniMax/M2.7-flash"
        new_provider = "minimax"
    elif model_choice == "3":
        new_model = "gpt-4o"
        new_provider = "openai"
    elif model_choice == "4":
        new_model = "claude-sonnet-4-20250514"
        new_provider = "anthropic"
    else:
        new_model = input("  Enter model name: ").strip()
        new_provider = "custom"

    # Update .env
    if env_file.exists():
        lines = env_file.read_text().splitlines()
    else:
        lines = []

    new_lines = []
    for line in lines:
        if line.startswith("MIMIRAETHER_MODEL="):
            new_lines.append(f"MIMIRAETHER_MODEL={new_model}")
        elif line.startswith("MIMIRAETHER_PROVIDER="):
            new_lines.append(f"MIMIRAETHER_PROVIDER={new_provider}")
        else:
            new_lines.append(line)

    if not any(l.startswith("MIMIRAETHER_MODEL=") for l in new_lines):
        new_lines.append(f"MIMIRAETHER_MODEL={new_model}")
    if not any(l.startswith("MIMIRAETHER_PROVIDER=") for l in new_lines):
        new_lines.append(f"MIMIRAETHER_PROVIDER={new_provider}")

    env_file.write_text("\n".join(new_lines) + "\n")

    print()
    print(f"  Model updated to: {new_model} ({new_provider})")
    print()


def cmd_gateway(args):
    """Gateway management commands."""
    action = getattr(args, "gateway_action", None)

    if action is None:
        print("  Available gateway commands:")
        print("    mimiraether gateway start   - Start gateway")
        print("    mimiraether gateway stop    - Stop gateway")
        print("    mimiraether gateway status  - Show gateway status")
        return

    if action == "start":
        print("  Starting MimirAether gateway...")
        print("  Note: Gateway service requires OpenClaw to be running")
        try:
            from mimiraether_constants import get_mimiraether_home
            home = get_mimiraether_home()
            gateway_dir = home / "gateway"
            if not gateway_dir.exists():
                print(f"  Creating gateway directory at {gateway_dir}")
                gateway_dir.mkdir(parents=True, exist_ok=True)
            print("  Gateway start command issued.")
        except Exception as e:
            print(f"  Error: {e}")
    elif action == "stop":
        print("  Stopping MimirAether gateway...")
        print("  Note: Use openclaw gateway stop to stop the gateway service")
    elif action == "status":
        print("  MimirAether Gateway Status")
        print("  " + "=" * 50)
        try:
            from mimiraether_constants import get_mimiraether_home
            home = get_mimiraether_home()
            sessions_dir = home / "sessions"
            if sessions_dir.exists():
                print(f"  Sessions dir: {sessions_dir}")
            else:
                print("  No sessions directory yet.")
        except Exception as e:
            print(f"  Error: {e}")


def cmd_cron(args):
    """Cron job management."""
    cron_action = getattr(args, "cron_action", None)

    if cron_action is None or cron_action == "list":
        print()
        print("  MimirAether Scheduled Tasks")
        print("  " + "=" * 50)
        print()
        print("  No scheduled tasks configured.")
        print()
        print("  Use the scheduler API to manage tasks:")
        print("  - Health checks")
        print("  - Self-evolution tasks")
        print("  - Report generation")
        print()
    elif cron_action == "status":
        print("  Scheduler: Not running (use openclaw cron to manage)")
    else:
        print(f"  Unknown cron action: {cron_action}")


def cmd_logs(args):
    """View recent logs."""
    import re
    from mimiraether_constants import get_mimiraether_home

    lines = getattr(args, "lines", 50)
    error_only = getattr(args, "errors", False)

    home = get_mimiraether_home()
    log_file = home / "logs" / "agent.log"

    print()
    if not log_file.exists():
        print("  No log file found.")
        return

    try:
        all_lines = log_file.read_text().splitlines()
        if error_only:
            all_lines = [l for l in all_lines if "ERROR" in l or "error" in l]
        recent = all_lines[-lines:]
        print(f"  Recent {'error ' if error_only else ''}logs ({len(recent)} lines):")
        print("  " + "-" * 50)
        for line in recent:
            # Strip timestamp for cleaner display
            line = re.sub(r'^\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[^\s]*\s+', '', line)
            print(f"  {line}")
    except Exception as e:
        print(f"  Error reading logs: {e}")
    print()


def cmd_config(args):
    """Show current configuration."""
    from mimiraether_constants import get_mimiraether_home

    print()
    print("  MimirAether Configuration")
    print("  " + "=" * 50)
    print()

    home = get_mimiraether_home()
    env_file = home / ".env"

    print(f"  Home directory: {home}")
    print()

    if env_file.exists():
        print("  .env configuration:")
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if "API_KEY" in line or "SECRET" in line or "TOKEN" in line:
                    # Mask sensitive values
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1]
                        if val:
                            line = f"{parts[0]}={val[:4]}{'*' * (len(val) - 4) if len(val) > 4 else '****'}"
                print(f"  {line}")
    else:
        print("  No .env file found (use 'mimiraether setup' to create)")

    print()

if __name__ == "__main__":
    main()
