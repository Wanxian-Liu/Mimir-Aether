#!/usr/bin/env python3
"""
MimirAether CLI - Main entry point.

Usage:
    mimir                     # Interactive chat (default)
    mimir chat                # Interactive chat
    mimir gateway             # Run gateway in foreground
    mimir gateway start       # Start gateway as service
    mimir gateway stop        # Stop gateway service
    mimir gateway status      # Show gateway status
    mimir gateway install     # Install gateway service
    mimir gateway uninstall   # Uninstall gateway service
    mimir setup               # Interactive setup wizard
    mimir logout              # Clear stored authentication
    mimir status              # Show status of all components
    mimir cron                # Manage cron jobs
    mimir cron list           # List cron jobs
    mimir cron status         # Check if cron scheduler is running
    mimir doctor              # Check configuration and dependencies
    mimir honcho setup                    # Configure Honcho AI memory integration
    mimir honcho status                   # Show Honcho config and connection status
    mimir honcho sessions                 # List directory → session name mappings
    mimir honcho map <name>               # Map current directory to a session name
    mimir honcho peer                     # Show peer names and dialectic settings
    mimir honcho peer --user NAME         # Set user peer name
    mimir honcho peer --ai NAME           # Set AI peer name
    mimir honcho peer --reasoning LEVEL   # Set dialectic reasoning level
    mimir honcho mode                     # Show current memory mode
    mimir honcho mode [hybrid|honcho|local]  # Set memory mode
    mimir honcho tokens                   # Show token budget settings
    mimir honcho tokens --context N       # Set session.context() token cap
    mimir honcho tokens --dialectic N     # Set dialectic result char cap
    mimir honcho identity                 # Show AI peer identity representation
    mimir honcho identity <file>          # Seed AI peer identity from a file (SOUL.md etc.)
    mimir honcho migrate                  # Step-by-step migration guide: OpenClaw native → MimirAether + Honcho
    mimir version             Show version
    mimir update              Update to latest version
    mimir uninstall           Uninstall MimirAether
    mimir acp                 Run as an ACP server for editor integration
    mimir sessions browse     Interactive session picker with search

    mimir claw migrate --dry-run  # Preview migration without changes
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

def _require_tty(command_name: str) -> None:
    """Exit with a clear error if stdin is not a terminal.

    Interactive TUI commands (mimir tools, mimir setup, mimir model) use
    curses or input() prompts that spin at 100% CPU when stdin is a pipe.
    This guard prevents accidental non-interactive invocation.
    """
    if not sys.stdin.isatty():
        print(
            f"Error: 'mimir {command_name}' requires an interactive terminal.\n"
            f"It cannot be run through a pipe or non-interactive subprocess.\n"
            f"Run it directly in your terminal instead.",
            file=sys.stderr,
        )
        sys.exit(1)


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Profile override — MUST happen before any mimir module import.
#
# Many modules cache HERMES_HOME at import time (module-level constants).
# We intercept --profile/-p from sys.argv here and set the env var so that
# every subsequent ``os.getenv("HERMES_HOME", ...)`` resolves correctly.
# The flag is stripped from sys.argv so argparse never sees it.
# Falls back to ~/.mimir/active_profile for sticky default.
# ---------------------------------------------------------------------------
def _apply_profile_override() -> None:
    """Pre-parse --profile/-p and set HERMES_HOME before module imports."""
    argv = sys.argv[1:]
    profile_name = None
    consume = 0

    # 1. Check for explicit -p / --profile flag
    for i, arg in enumerate(argv):
        if arg in ("--profile", "-p") and i + 1 < len(argv):
            profile_name = argv[i + 1]
            consume = 2
            break
        elif arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]
            consume = 1
            break

    # 2. If no flag, check active_profile in the mimir root
    if profile_name is None:
        try:
            from mimir_constants import get_default_hermes_root
            active_path = get_default_hermes_root() / "active_profile"
            if active_path.exists():
                name = active_path.read_text().strip()
                if name and name != "default":
                    profile_name = name
                    consume = 0  # don't strip anything from argv
        except (UnicodeDecodeError, OSError):
            pass  # corrupted file, skip

    # 3. If we found a profile, resolve and set HERMES_HOME
    if profile_name is not None:
        try:
            from mimir_cli.profiles import resolve_profile_env
            hermes_home = resolve_profile_env(profile_name)
        except (ValueError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            # A bug in profiles.py must NEVER prevent mimir from starting
            print(f"Warning: profile override failed ({exc}), using default", file=sys.stderr)
            return
        os.environ["HERMES_HOME"] = hermes_home
        # Strip the flag from argv so argparse doesn't choke
        if consume > 0:
            for i, arg in enumerate(argv):
                if arg in ("--profile", "-p"):
                    start = i + 1  # +1 because argv is sys.argv[1:]
                    sys.argv = sys.argv[:start] + sys.argv[start + consume:]
                    break
                elif arg.startswith("--profile="):
                    start = i + 1
                    sys.argv = sys.argv[:start] + sys.argv[start + 1:]
                    break

_apply_profile_override()

# Load .env from ~/.mimir/.env first, then project root as dev fallback.
# User-managed env files should override stale shell exports on restart.
from mimir_cli.config import get_hermes_home
from mimir_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv(project_env=PROJECT_ROOT / '.env')

# Initialize centralized file logging early — all `mimir` subcommands
# (chat, setup, gateway, config, etc.) write to agent.log + errors.log.
try:
    from mimiraether_logging import setup_logging as _setup_logging
    _setup_logging(mode="cli")
except Exception:
    pass  # best-effort — don't crash the CLI if logging setup fails

# Apply IPv4 preference early, before any HTTP clients are created.
try:
    from mimir_cli.config import load_config as _load_config_early
    from mimir_constants import apply_ipv4_preference as _apply_ipv4
    _early_cfg = _load_config_early()
    _net = _early_cfg.get("network", {})
    if isinstance(_net, dict) and _net.get("force_ipv4"):
        _apply_ipv4(force=True)
    del _early_cfg, _net
except Exception:
    pass  # best-effort — don't crash if config isn't available yet

import logging
import time as _time
from datetime import datetime

from mimir_cli import __version__, __release_date__
from mimir_constants import OPENROUTER_BASE_URL
from mimir_cli.paths import openclaw_migration_source_default

_OPENCLAW_MIGRATE_SOURCE_DEFAULT = str(openclaw_migration_source_default()).replace(
    str(Path.home()), "~", 1
)

logger = logging.getLogger(__name__)

from mimir_cli.model_wizard import select_provider_and_model
from mimir_cli.session_picker import (
    _session_browse_picker,
    _resolve_last_cli_session,
    _resolve_session_by_name_or_id,
)
from mimir_cli.container_cli import _probe_container, _exec_in_container
from mimir_cli.update_command import cmd_update
from mimir_cli.profile_command import cmd_profile, _coalesce_session_name_args
from mimir_cli.cli_subparsers_setup import configure_parser_part1
from mimir_cli.cli_subparsers_bind import configure_parser_part2

def _require_tty(command_name: str) -> None:
    """Exit with a clear error if stdin is not a terminal.

    Interactive TUI commands (mimir tools, mimir setup, mimir model) use
    curses or input() prompts that spin at 100% CPU when stdin is a pipe.
    This guard prevents accidental non-interactive invocation.
    """
    if not sys.stdin.isatty():
        print(
            f"Error: 'mimir {command_name}' requires an interactive terminal.\n"
            f"It cannot be run through a pipe or non-interactive subprocess.\n"
            f"Run it directly in your terminal instead.",
            file=sys.stderr,
        )
        sys.exit(1)


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Profile override — MUST happen before any mimir module import.
#
# Many modules cache HERMES_HOME at import time (module-level constants).
# We intercept --profile/-p from sys.argv here and set the env var so that
# every subsequent ``os.getenv("HERMES_HOME", ...)`` resolves correctly.
# The flag is stripped from sys.argv so argparse never sees it.
# Falls back to ~/.mimir/active_profile for sticky default.
# ---------------------------------------------------------------------------

def _apply_profile_override() -> None:
    """Pre-parse --profile/-p and set HERMES_HOME before module imports."""
    argv = sys.argv[1:]
    profile_name = None
    consume = 0

    # 1. Check for explicit -p / --profile flag
    for i, arg in enumerate(argv):
        if arg in ("--profile", "-p") and i + 1 < len(argv):
            profile_name = argv[i + 1]
            consume = 2
            break
        elif arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]
            consume = 1
            break

    # 2. If no flag, check active_profile in the mimir root
    if profile_name is None:
        try:
            from mimir_constants import get_default_hermes_root
            active_path = get_default_hermes_root() / "active_profile"
            if active_path.exists():
                name = active_path.read_text().strip()
                if name and name != "default":
                    profile_name = name
                    consume = 0  # don't strip anything from argv
        except (UnicodeDecodeError, OSError):
            pass  # corrupted file, skip

    # 3. If we found a profile, resolve and set HERMES_HOME
    if profile_name is not None:
        try:
            from mimir_cli.profiles import resolve_profile_env
            hermes_home = resolve_profile_env(profile_name)
        except (ValueError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            # A bug in profiles.py must NEVER prevent mimir from starting
            print(f"Warning: profile override failed ({exc}), using default", file=sys.stderr)
            return
        os.environ["HERMES_HOME"] = hermes_home
        # Strip the flag from argv so argparse doesn't choke
        if consume > 0:
            for i, arg in enumerate(argv):
                if arg in ("--profile", "-p"):
                    start = i + 1  # +1 because argv is sys.argv[1:]
                    sys.argv = sys.argv[:start] + sys.argv[start + consume:]
                    break
                elif arg.startswith("--profile="):
                    start = i + 1
                    sys.argv = sys.argv[:start] + sys.argv[start + 1:]
                    break

_apply_profile_override()

# Load .env from ~/.mimir/.env first, then project root as dev fallback.
# User-managed env files should override stale shell exports on restart.
from mimir_cli.config import get_hermes_home
from mimir_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv(project_env=PROJECT_ROOT / '.env')

# Initialize centralized file logging early — all `mimir` subcommands
# (chat, setup, gateway, config, etc.) write to agent.log + errors.log.
try:
    from mimiraether_logging import setup_logging as _setup_logging
    _setup_logging(mode="cli")
except Exception:
    pass  # best-effort — don't crash the CLI if logging setup fails

# Apply IPv4 preference early, before any HTTP clients are created.
try:
    from mimir_cli.config import load_config as _load_config_early
    from mimir_constants import apply_ipv4_preference as _apply_ipv4
    _early_cfg = _load_config_early()
    _net = _early_cfg.get("network", {})
    if isinstance(_net, dict) and _net.get("force_ipv4"):
        _apply_ipv4(force=True)
    del _early_cfg, _net
except Exception:
    pass  # best-effort — don't crash if config isn't available yet

import logging
import time as _time
from datetime import datetime

from mimir_cli import __version__, __release_date__
from mimir_constants import OPENROUTER_BASE_URL
from mimir_cli.paths import openclaw_migration_source_default

_OPENCLAW_MIGRATE_SOURCE_DEFAULT = str(openclaw_migration_source_default()).replace(
    str(Path.home()), "~", 1
)

logger = logging.getLogger(__name__)

def _has_any_provider_configured() -> bool:
    """Check if at least one inference provider is usable."""
    from mimir_cli.config import get_env_path, get_hermes_home, load_config
    from mimir_cli.auth import get_auth_status

    # Determine whether MimirAether itself has been explicitly configured (model
    # in config that isn't the hardcoded default). Used below to gate external
    # tool credentials (Claude Code, Codex CLI) that shouldn't silently skip
    # the setup wizard on a fresh install.
    from mimir_cli.config import DEFAULT_CONFIG
    _DEFAULT_MODEL = DEFAULT_CONFIG.get("model", "")
    cfg = load_config()
    model_cfg = cfg.get("model")
    if isinstance(model_cfg, dict):
        _model_name = (model_cfg.get("default") or "").strip()
    elif isinstance(model_cfg, str):
        _model_name = model_cfg.strip()
    else:
        _model_name = ""
    _has_hermes_config = _model_name and _model_name != _DEFAULT_MODEL

    # Check env vars (may be set by .env or shell).
    # OPENAI_BASE_URL alone counts — local models (vLLM, llama.cpp, etc.)
    # often don't require an API key.
    from mimir_cli.auth import PROVIDER_REGISTRY

    # Collect all provider env vars
    provider_env_vars = {"OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "OPENAI_BASE_URL"}
    for pconfig in PROVIDER_REGISTRY.values():
        if pconfig.auth_type == "api_key":
            provider_env_vars.update(pconfig.api_key_env_vars)
    if any(os.getenv(v) for v in provider_env_vars):
        return True

    # Check .env file for keys
    env_file = get_env_path()
    if env_file.exists():
        try:
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip("'\"")
                if key.strip() in provider_env_vars and val:
                    return True
        except Exception:
            pass

    # Check provider-specific auth fallbacks (for example, Copilot via gh auth).
    try:
        for provider_id, pconfig in PROVIDER_REGISTRY.items():
            if pconfig.auth_type != "api_key":
                continue
            status = get_auth_status(provider_id)
            if status.get("logged_in"):
                return True
    except Exception:
        pass

    # Check for Nous Portal OAuth credentials
    auth_file = get_hermes_home() / "auth.json"
    if auth_file.exists():
        try:
            import json
            auth = json.loads(auth_file.read_text())
            active = auth.get("active_provider")
            if active:
                status = get_auth_status(active)
                if status.get("logged_in"):
                    return True
        except Exception:
            pass


    # Check config.yaml — if model is a dict with an explicit provider set,
    # the user has gone through setup (fresh installs have model as a plain
    # string).  Also covers custom endpoints that store api_key/base_url in
    # config rather than .env.
    if isinstance(model_cfg, dict):
        cfg_provider = (model_cfg.get("provider") or "").strip()
        cfg_base_url = (model_cfg.get("base_url") or "").strip()
        cfg_api_key = (model_cfg.get("api_key") or "").strip()
        if cfg_provider or cfg_base_url or cfg_api_key:
            return True

    # Check for Claude Code OAuth credentials (~/.claude/.credentials.json)
    # Only count these if MimirAether has been explicitly configured — Claude Code
    # being installed doesn't mean the user wants MimirAether to use their tokens.
    if _has_hermes_config:
        try:
            from agent.anthropic_adapter import read_claude_code_credentials, is_claude_code_token_valid
            creds = read_claude_code_credentials()
            if creds and (is_claude_code_token_valid(creds) or creds.get("refreshToken")):
                return True
        except Exception:
            pass

    return False

def cmd_chat(args):
    """Run interactive chat CLI."""
    # Resolve --continue into --resume with the latest CLI session or by name
    continue_val = getattr(args, "continue_last", None)
    if continue_val and not getattr(args, "resume", None):
        if isinstance(continue_val, str):
            # -c "session name" — resolve by title or ID
            resolved = _resolve_session_by_name_or_id(continue_val)
            if resolved:
                args.resume = resolved
            else:
                print(f"No session found matching '{continue_val}'.")
                print("Use 'mimir sessions list' to see available sessions.")
                sys.exit(1)
        else:
            # -c with no argument — continue the most recent session
            last_id = _resolve_last_cli_session()
            if last_id:
                args.resume = last_id
            else:
                print("No previous CLI session found to continue.")
                sys.exit(1)

    # Resolve --resume by title if it's not a direct session ID
    resume_val = getattr(args, "resume", None)
    if resume_val:
        resolved = _resolve_session_by_name_or_id(resume_val)
        if resolved:
            args.resume = resolved
        # If resolution fails, keep the original value — _init_agent will
        # report "Session not found" with the original input

    # First-run guard: check if any provider is configured before launching
    if not _has_any_provider_configured():
        print()
        print("It looks like MimirAether isn't configured yet -- no API keys or providers found.")
        print()
        print("  Run:  mimir setup")
        print()

        from mimir_cli.setup import is_interactive_stdin, print_noninteractive_setup_guidance

        if not is_interactive_stdin():
            print_noninteractive_setup_guidance(
                "No interactive TTY detected for the first-run setup prompt."
            )
            sys.exit(1)

        try:
            reply = input("Run setup now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            reply = "n"
        if reply in ("", "y", "yes"):
            cmd_setup(args)
            return
        print()
        print("You can run 'mimir setup' at any time to configure.")
        sys.exit(1)

    # Start update check in background (runs while other init happens)
    try:
        from mimir_cli.banner import prefetch_update_check
        prefetch_update_check()
    except Exception:
        pass

    # Sync bundled skills on every CLI launch (fast -- skips unchanged skills)
    try:
        from tools.skills_sync import sync_skills
        sync_skills(quiet=True)
    except Exception:
        pass

    # --yolo: bypass all dangerous command approvals
    if getattr(args, "yolo", False):
        os.environ["HERMES_YOLO_MODE"] = "1"

    # --source: tag session source for filtering (e.g. 'tool' for third-party integrations)
    if getattr(args, "source", None):
        os.environ["HERMES_SESSION_SOURCE"] = args.source

    from mimir_cli.chat_runner import run_chat

    try:
        run_chat(args)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_gateway(args):
    """Gateway management commands."""
    from mimir_cli.gateway import gateway_command
    gateway_command(args)

def cmd_whatsapp(args):
    """Set up WhatsApp: choose mode, configure, install bridge, pair via QR."""
    _require_tty("whatsapp")
    import subprocess
    from pathlib import Path
    from mimir_cli.config import get_env_value, save_env_value

    print()
    print("⚕ WhatsApp Setup")
    print("=" * 50)

    # ── Step 1: Choose mode ──────────────────────────────────────────────
    current_mode = get_env_value("WHATSAPP_MODE") or ""
    if not current_mode:
        print()
        print("How will you use WhatsApp with MimirAether?")
        print()
        print("  1. Separate bot number (recommended)")
        print("     People message the bot's number directly — cleanest experience.")
        print("     Requires a second phone number with WhatsApp installed on a device.")
        print()
        print("  2. Personal number (self-chat)")
        print("     You message yourself to talk to the agent.")
        print("     Quick to set up, but the UX is less intuitive.")
        print()
        try:
            choice = input("  Choose [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            return

        if choice == "1":
            save_env_value("WHATSAPP_MODE", "bot")
            wa_mode = "bot"
            print("  ✓ Mode: separate bot number")
            print()
            print("  ┌─────────────────────────────────────────────────┐")
            print("  │  Getting a second number for the bot:           │")
            print("  │                                                 │")
            print("  │  Easiest: Install WhatsApp Business (free app)  │")
            print("  │  on your phone with a second number:            │")
            print("  │    • Dual-SIM: use your 2nd SIM slot            │")
            print("  │    • Google Voice: free US number (voice.google) │")
            print("  │    • Prepaid SIM: $3-10, verify once            │")
            print("  │                                                 │")
            print("  │  WhatsApp Business runs alongside your personal │")
            print("  │  WhatsApp — no second phone needed.             │")
            print("  └─────────────────────────────────────────────────┘")
        else:
            save_env_value("WHATSAPP_MODE", "self-chat")
            wa_mode = "self-chat"
            print("  ✓ Mode: personal number (self-chat)")
    else:
        wa_mode = current_mode
        mode_label = "separate bot number" if wa_mode == "bot" else "personal number (self-chat)"
        print(f"\n✓ Mode: {mode_label}")

    # ── Step 2: Enable WhatsApp ──────────────────────────────────────────
    print()
    current = get_env_value("WHATSAPP_ENABLED")
    if current and current.lower() == "true":
        print("✓ WhatsApp is already enabled")
    else:
        save_env_value("WHATSAPP_ENABLED", "true")
        print("✓ WhatsApp enabled")

    # ── Step 3: Allowed users ────────────────────────────────────────────
    current_users = get_env_value("WHATSAPP_ALLOWED_USERS") or ""
    if current_users:
        print(f"✓ Allowed users: {current_users}")
        try:
            response = input("\n  Update allowed users? [y/N] ").strip()
        except (EOFError, KeyboardInterrupt):
            response = "n"
        if response.lower() in ("y", "yes"):
            if wa_mode == "bot":
                phone = input("  Phone numbers that can message the bot (comma-separated): ").strip()
            else:
                phone = input("  Your phone number (e.g. 15551234567): ").strip()
            if phone:
                save_env_value("WHATSAPP_ALLOWED_USERS", phone.replace(" ", ""))
                print(f"  ✓ Updated to: {phone}")
    else:
        print()
        if wa_mode == "bot":
            print("  Who should be allowed to message the bot?")
            phone = input("  Phone numbers (comma-separated, or * for anyone): ").strip()
        else:
            phone = input("  Your phone number (e.g. 15551234567): ").strip()
        if phone:
            save_env_value("WHATSAPP_ALLOWED_USERS", phone.replace(" ", ""))
            print(f"  ✓ Allowed users set: {phone}")
        else:
            print("  ⚠ No allowlist — the agent will respond to ALL incoming messages")

    # ── Step 4: Install bridge dependencies ──────────────────────────────
    project_root = Path(__file__).resolve().parents[1]
    bridge_dir = project_root / "scripts" / "whatsapp-bridge"
    bridge_script = bridge_dir / "bridge.js"

    if not bridge_script.exists():
        print(f"\n✗ Bridge script not found at {bridge_script}")
        return

    if not (bridge_dir / "node_modules").exists():
        print("\n→ Installing WhatsApp bridge dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(bridge_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  ✗ npm install failed: {result.stderr}")
            return
        print("  ✓ Dependencies installed")
    else:
        print("✓ Bridge dependencies already installed")

    # ── Step 5: Check for existing session ───────────────────────────────
    session_dir = get_hermes_home() / "whatsapp" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)

    if (session_dir / "creds.json").exists():
        print("✓ Existing WhatsApp session found")
        try:
            response = input("\n  Re-pair? This will clear the existing session. [y/N] ").strip()
        except (EOFError, KeyboardInterrupt):
            response = "n"
        if response.lower() in ("y", "yes"):
            import shutil
            shutil.rmtree(session_dir, ignore_errors=True)
            session_dir.mkdir(parents=True, exist_ok=True)
            print("  ✓ Session cleared")
        else:
            print("\n✓ WhatsApp is configured and paired!")
            print("  Start the gateway with: mimir gateway")
            return

    # ── Step 6: QR code pairing ──────────────────────────────────────────
    print()
    print("─" * 50)
    if wa_mode == "bot":
        print("📱 Open WhatsApp (or WhatsApp Business) on the")
        print("   phone with the BOT's number, then scan:")
    else:
        print("📱 Open WhatsApp on your phone, then scan:")
    print()
    print("   Settings → Linked Devices → Link a Device")
    print("─" * 50)
    print()

    try:
        subprocess.run(
            ["node", str(bridge_script), "--pair-only", "--session", str(session_dir)],
            cwd=str(bridge_dir),
        )
    except KeyboardInterrupt:
        pass

    # ── Step 7: Post-pairing ─────────────────────────────────────────────
    print()
    if (session_dir / "creds.json").exists():
        print("✓ WhatsApp paired successfully!")
        print()
        if wa_mode == "bot":
            print("  Next steps:")
            print("    1. Start the gateway:  mimir gateway")
            print("    2. Send a message to the bot's WhatsApp number")
            print("    3. The agent will reply automatically")
            print()
            print("  Tip: Agent responses are prefixed with '⚕ MimirAether'")
        else:
            print("  Next steps:")
            print("    1. Start the gateway:  mimir gateway")
            print("    2. Open WhatsApp → Message Yourself")
            print("    3. Type a message — the agent will reply")
            print()
            print("  Tip: Agent responses are prefixed with '⚕ MimirAether'")
            print("  so you can tell them apart from your own messages.")
        print()
        print("  Or install as a service: mimir gateway install")
    else:
        print("⚠ Pairing may not have completed. Run 'mimir whatsapp' to try again.")

def cmd_setup(args):
    """Interactive setup wizard."""
    from mimir_cli.setup import run_setup_wizard
    run_setup_wizard(args)

def cmd_model(args):
    """Select default model — starts with provider selection, then model picker."""
    _require_tty("model")
    select_provider_and_model(args=args)

def cmd_login(args):
    """Authenticate MimirAether CLI with a provider."""
    from mimir_cli.auth import login_command
    login_command(args)

def cmd_logout(args):
    """Clear provider authentication."""
    from mimir_cli.auth import logout_command
    logout_command(args)

def cmd_auth(args):
    """Manage pooled credentials."""
    from mimir_cli.auth_commands import auth_command
    auth_command(args)

def cmd_status(args):
    """Show status of all components."""
    from mimir_cli.status import show_status
    show_status(args)

def cmd_cron(args):
    """Cron job management."""
    from mimir_cli.cron import cron_command
    cron_command(args)

def cmd_webhook(args):
    """Webhook subscription management."""
    from mimir_cli.webhook import webhook_command
    webhook_command(args)

def cmd_doctor(args):
    """Check configuration and dependencies."""
    from mimir_cli.doctor import run_doctor
    run_doctor(args)

def cmd_dump(args):
    """Dump setup summary for support/debugging."""
    from mimir_cli.dump import run_dump
    run_dump(args)

def cmd_debug(args):
    """Debug tools (share report, etc.)."""
    from mimir_cli.debug import run_debug
    run_debug(args)

def cmd_config(args):
    """Configuration management."""
    from mimir_cli.config import config_command
    config_command(args)

def cmd_backup(args):
    """Back up MimirAether home directory to a zip file."""
    if getattr(args, "quick", False):
        from mimir_cli.backup import run_quick_backup
        run_quick_backup(args)
    else:
        from mimir_cli.backup import run_backup
        run_backup(args)

def cmd_import(args):
    """Restore a MimirAether backup from a zip file."""
    from mimir_cli.backup import run_import
    run_import(args)

def cmd_version(args):
    """Show version."""
    print(f"MimirAether v{__version__} ({__release_date__})")
    print(f"Project: {PROJECT_ROOT}")
    
    # Show Python version
    print(f"Python: {sys.version.split()[0]}")
    
    # Check for key dependencies
    try:
        import openai
        print(f"OpenAI SDK: {openai.__version__}")
    except ImportError:
        print("OpenAI SDK: Not installed")

    # Show update status (synchronous — acceptable since user asked for version info)
    try:
        from mimir_cli.banner import check_for_updates
        from mimir_cli.config import recommended_update_command
        behind = check_for_updates()
        if behind and behind > 0:
            commits_word = "commit" if behind == 1 else "commits"
            print(
                f"Update available: {behind} {commits_word} behind — "
                f"run '{recommended_update_command()}'"
            )
        elif behind == 0:
            print("Up to date")
    except Exception:
        pass

def cmd_uninstall(args):
    """Uninstall MimirAether."""
    _require_tty("uninstall")
    from mimir_cli.uninstall import run_uninstall
    run_uninstall(args)

def cmd_dashboard(args):
    """Start the web UI server."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("Web UI dependencies not installed.")
        print("Install them with:  pip install mimir-agent[web]")
        sys.exit(1)

    if not _build_web_ui(PROJECT_ROOT / "web", fatal=True):
        sys.exit(1)

    from mimir_cli.web_server import start_server
    start_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )

def cmd_completion(args):
    """Print shell completion script."""
    from mimir_cli.profiles import generate_bash_completion, generate_zsh_completion
    shell = getattr(args, "shell", "bash")
    if shell == "zsh":
        print(generate_zsh_completion())
    else:
        print(generate_bash_completion())

def cmd_logs(args):
    """View and filter MimirAether log files."""
    from mimir_cli.logs import tail_log, list_logs

    log_name = getattr(args, "log_name", "agent") or "agent"

    if log_name == "list":
        list_logs()
        return

    tail_log(
        log_name,
        num_lines=getattr(args, "lines", 50),
        follow=getattr(args, "follow", False),
        level=getattr(args, "level", None),
        session=getattr(args, "session", None),
        since=getattr(args, "since", None),
        component=getattr(args, "component", None),
    )

def main():
    """Main entry point for mimir CLI."""
    parser, subparsers = configure_parser_part1()
    configure_parser_part2(parser, subparsers)

    from mimir_cli.config import get_container_exec_info

    container_info = get_container_exec_info()
    if container_info:
        _exec_in_container(container_info, sys.argv[1:])
        sys.exit(1)

    _processed_argv = _coalesce_session_name_args(sys.argv[1:])
    args = parser.parse_args(_processed_argv)

    if getattr(args, "version", False):
        cmd_version(args)
        return

    if (getattr(args, "resume", None) or getattr(args, "continue_last", None)) and args.command is None:
        args.command = "chat"
        args.query = None
        args.model = None
        args.provider = None
        args.toolsets = None
        args.verbose = False
        if not hasattr(args, "worktree"):
            args.worktree = False
        cmd_chat(args)
        return

    if args.command is None:
        args.query = None
        args.model = None
        args.provider = None
        args.toolsets = None
        args.verbose = False
        args.resume = None
        args.continue_last = None
        if not hasattr(args, "worktree"):
            args.worktree = False
        cmd_chat(args)
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
