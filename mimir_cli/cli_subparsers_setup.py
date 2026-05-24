"""Argparse subparser definitions — part 1 (P1-LONG-GOD)."""
from __future__ import annotations

import argparse
import logging
import sys

from mimir_cli import __version__, __release_date__
from mimir_cli.main_dispatch import get_command_handlers, _require_tty

logger = logging.getLogger(__name__)


def configure_parser_part1():
    """Build root parser, top-level flags, and first-half subcommands."""
    handlers = get_command_handlers()
    """Main entry point for mimir CLI."""
    parser = argparse.ArgumentParser(
        prog="mimir",
        description="MimirAether - AI assistant with tool-calling capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Examples:
    mimir                        Start interactive chat
    mimir chat -q "Hello"        Single query mode
    mimir -c                     Resume the most recent session
    mimir -c "my project"        Resume a session by name (latest in lineage)
    mimir --resume <session_id>  Resume a specific session by ID
    mimir setup                  Run setup wizard
    mimir logout                 Clear stored authentication
    mimir auth add <provider>    Add a pooled credential
    mimir auth list              List pooled credentials
    mimir auth remove <p> <t>    Remove pooled credential by index, id, or label
    mimir auth reset <provider>  Clear exhaustion status for a provider
    mimir model                  Select default model
    mimir config                 View configuration
    mimir config edit            Edit config in $EDITOR
    mimir config set model gpt-4 Set a config value
    mimir gateway                Run messaging gateway
    mimir -s mimir-agent-dev,github-auth
    mimir -w                     Start in isolated git worktree
    mimir gateway install        Install gateway background service
    mimir sessions list          List past sessions
    mimir sessions browse        Interactive session picker
    mimir sessions rename ID T   Rename/title a session
    mimir logs                   View agent.log (last 50 lines)
    mimir logs -f                Follow agent.log in real time
    mimir logs errors            View errors.log
    mimir logs --since 1h        Lines from the last hour
    mimir debug share             Upload debug report for support
    mimir update                 Update to latest version

    For more help on a command:
    mimir <command> --help
    """
    )

    parser.add_argument(
        "--version", "-V",
        action="store_true",
        help="Show version and exit"
    )
    parser.add_argument(
        "--resume", "-r",
        metavar="SESSION",
        default=None,
        help="Resume a previous session by ID or title"
    )
    parser.add_argument(
        "--continue", "-c",
        dest="continue_last",
        nargs="?",
        const=True,
        default=None,
        metavar="SESSION_NAME",
        help="Resume a session by name, or the most recent if no name given"
    )
    parser.add_argument(
        "--worktree", "-w",
        action="store_true",
        default=False,
        help="Run in an isolated git worktree (for parallel agents)"
    )
    parser.add_argument(
        "--skills", "-s",
        action="append",
        default=None,
        help="Preload one or more skills for the session (repeat flag or comma-separate)"
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Bypass all dangerous command approval prompts (use at your own risk)"
    )
    parser.add_argument(
        "--pass-session-id",
        action="store_true",
        default=False,
        help="Include the session ID in the agent's system prompt"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # =========================================================================
    # chat command
    # =========================================================================
    chat_parser = subparsers.add_parser(
        "chat",
        help="Interactive chat with the agent",
        description="Start an interactive chat session with MimirAether"
    )
    chat_parser.add_argument(
        "-q", "--query",
        help="Single query (non-interactive mode)"
    )
    chat_parser.add_argument(
        "--image",
        help="Optional local image path to attach to a single query"
    )
    chat_parser.add_argument(
        "-m", "--model",
        help="Model to use (e.g., anthropic/claude-sonnet-4)"
    )
    chat_parser.add_argument(
        "-t", "--toolsets",
        help="Comma-separated toolsets to enable"
    )
    chat_parser.add_argument(
        "-s", "--skills",
        action="append",
        default=argparse.SUPPRESS,
        help="Preload one or more skills for the session (repeat flag or comma-separate)"
    )
    chat_parser.add_argument(
        "--provider",
        choices=["auto", "openrouter", "nous", "openai-codex", "copilot-acp", "copilot", "anthropic", "gemini", "huggingface", "zai", "kimi-coding", "kimi-coding-cn", "minimax", "minimax-cn", "kilocode", "xiaomi", "arcee"],
        default=None,
        help="Inference provider (default: auto)"
    )
    chat_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    chat_parser.add_argument(
        "-Q", "--quiet",
        action="store_true",
        help="Quiet mode for programmatic use: suppress banner, spinner, and tool previews. Only output the final response and session info."
    )
    chat_parser.add_argument(
        "--resume", "-r",
        metavar="SESSION_ID",
        default=argparse.SUPPRESS,
        help="Resume a previous session by ID (shown on exit)"
    )
    chat_parser.add_argument(
        "--continue", "-c",
        dest="continue_last",
        nargs="?",
        const=True,
        default=argparse.SUPPRESS,
        metavar="SESSION_NAME",
        help="Resume a session by name, or the most recent if no name given"
    )
    chat_parser.add_argument(
        "--worktree", "-w",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Run in an isolated git worktree (for parallel agents on the same repo)"
    )
    chat_parser.add_argument(
        "--checkpoints",
        action="store_true",
        default=False,
        help="Enable filesystem checkpoints before destructive file operations (use /rollback to restore)"
    )
    chat_parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        metavar="N",
        help="Maximum tool-calling iterations per conversation turn (default: 90, or agent.max_turns in config)"
    )
    chat_parser.add_argument(
        "--yolo",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Bypass all dangerous command approval prompts (use at your own risk)"
    )
    chat_parser.add_argument(
        "--pass-session-id",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Include the session ID in the agent's system prompt"
    )
    chat_parser.add_argument(
        "--source",
        default=None,
        help="Session source tag for filtering (default: cli). Use 'tool' for third-party integrations that should not appear in user session lists."
    )
    chat_parser.set_defaults(func=handlers['cmd_chat'])

    # =========================================================================
    # model command
    # =========================================================================
    model_parser = subparsers.add_parser(
        "model",
        help="Select default model and provider",
        description="Interactively select your inference provider and default model"
    )
    model_parser.add_argument(
        "--portal-url",
        help="Portal base URL for Nous login (default: production portal)"
    )
    model_parser.add_argument(
        "--inference-url",
        help="Inference API base URL for Nous login (default: production inference API)"
    )
    model_parser.add_argument(
        "--client-id",
        default=None,
        help="OAuth client id to use for Nous login (default: mimir-cli)"
    )
    model_parser.add_argument(
        "--scope",
        default=None,
        help="OAuth scope to request for Nous login"
    )
    model_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to open the browser automatically during Nous login"
    )
    model_parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout in seconds for Nous login (default: 15)"
    )
    model_parser.add_argument(
        "--ca-bundle",
        help="Path to CA bundle PEM file for Nous TLS verification"
    )
    model_parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification for Nous login (testing only)"
    )
    model_parser.set_defaults(func=handlers['cmd_model'])

    # =========================================================================
    # gateway command
    # =========================================================================
    gateway_parser = subparsers.add_parser(
        "gateway",
        help="Messaging gateway management",
        description="Manage the messaging gateway (Telegram, Discord, WhatsApp)"
    )
    gateway_subparsers = gateway_parser.add_subparsers(dest="gateway_command")

    # gateway run (default)
    gateway_run = gateway_subparsers.add_parser("run", help="Run gateway in foreground (recommended for WSL, Docker, Termux)")
    gateway_run.add_argument("-v", "--verbose", action="count", default=0,
                             help="Increase stderr log verbosity (-v=INFO, -vv=DEBUG)")
    gateway_run.add_argument("-q", "--quiet", action="store_true",
                             help="Suppress all stderr log output")
    gateway_run.add_argument("--replace", action="store_true",
                             help="Replace any existing gateway instance (useful for systemd)")

    # gateway start
    gateway_start = gateway_subparsers.add_parser("start", help="Start the installed systemd/launchd background service")
    gateway_start.add_argument("--system", action="store_true", help="Target the Linux system-level gateway service")

    # gateway stop
    gateway_stop = gateway_subparsers.add_parser("stop", help="Stop gateway service")
    gateway_stop.add_argument("--system", action="store_true", help="Target the Linux system-level gateway service")
    gateway_stop.add_argument("--all", action="store_true", help="Stop ALL gateway processes across all profiles")

    # gateway restart
    gateway_restart = gateway_subparsers.add_parser("restart", help="Restart gateway service")
    gateway_restart.add_argument("--system", action="store_true", help="Target the Linux system-level gateway service")

    # gateway status
    gateway_status = gateway_subparsers.add_parser("status", help="Show gateway status")
    gateway_status.add_argument("--deep", action="store_true", help="Deep status check")
    gateway_status.add_argument("--system", action="store_true", help="Target the Linux system-level gateway service")

    # gateway install
    gateway_install = gateway_subparsers.add_parser("install", help="Install gateway as a systemd/launchd background service")
    gateway_install.add_argument("--force", action="store_true", help="Force reinstall")
    gateway_install.add_argument("--system", action="store_true", help="Install as a Linux system-level service (starts at boot)")
    gateway_install.add_argument("--run-as-user", dest="run_as_user", help="User account the Linux system service should run as")

    # gateway uninstall
    gateway_uninstall = gateway_subparsers.add_parser("uninstall", help="Uninstall gateway service")
    gateway_uninstall.add_argument("--system", action="store_true", help="Target the Linux system-level gateway service")

    # gateway setup
    gateway_subparsers.add_parser("setup", help="Configure messaging platforms")

    gateway_parser.set_defaults(func=handlers['cmd_gateway'])

    # =========================================================================
    # setup command
    # =========================================================================
    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup wizard",
        description="Configure MimirAether with an interactive wizard. "
                    "Run a specific section: mimir setup model|tts|terminal|gateway|tools|agent"
    )
    setup_parser.add_argument(
        "section",
        nargs="?",
        choices=["model", "tts", "terminal", "gateway", "tools", "agent"],
        default=None,
        help="Run a specific setup section instead of the full wizard"
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (use defaults/env vars)"
    )
    setup_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset configuration to defaults"
    )
    setup_parser.set_defaults(func=handlers['cmd_setup'])

    # =========================================================================
    # whatsapp command
    # =========================================================================
    whatsapp_parser = subparsers.add_parser(
        "whatsapp",
        help="Set up WhatsApp integration",
        description="Configure WhatsApp and pair via QR code"
    )
    whatsapp_parser.set_defaults(func=handlers['cmd_whatsapp'])

    # =========================================================================
    # login command
    # =========================================================================
    login_parser = subparsers.add_parser(
        "login",
        help="Authenticate with an inference provider",
        description="Run OAuth device authorization flow for MimirAether CLI"
    )
    login_parser.add_argument(
        "--provider",
        choices=["nous", "openai-codex"],
        default=None,
        help="Provider to authenticate with (default: nous)"
    )
    login_parser.add_argument(
        "--portal-url",
        help="Portal base URL (default: production portal)"
    )
    login_parser.add_argument(
        "--inference-url",
        help="Inference API base URL (default: production inference API)"
    )
    login_parser.add_argument(
        "--client-id",
        default=None,
        help="OAuth client id to use (default: mimir-cli)"
    )
    login_parser.add_argument(
        "--scope",
        default=None,
        help="OAuth scope to request"
    )
    login_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to open the browser automatically"
    )
    login_parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout in seconds (default: 15)"
    )
    login_parser.add_argument(
        "--ca-bundle",
        help="Path to CA bundle PEM file for TLS verification"
    )
    login_parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (testing only)"
    )
    login_parser.set_defaults(func=handlers['cmd_login'])

    # =========================================================================
    # logout command
    # =========================================================================
    logout_parser = subparsers.add_parser(
        "logout",
        help="Clear authentication for an inference provider",
        description="Remove stored credentials and reset provider config"
    )
    logout_parser.add_argument(
        "--provider",
        choices=["nous", "openai-codex"],
        default=None,
        help="Provider to log out from (default: active provider)"
    )
    logout_parser.set_defaults(func=handlers['cmd_logout'])

    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage pooled provider credentials",
    )
    auth_subparsers = auth_parser.add_subparsers(dest="auth_action")
    auth_add = auth_subparsers.add_parser("add", help="Add a pooled credential")
    auth_add.add_argument("provider", help="Provider id (for example: anthropic, openai-codex, openrouter)")
    auth_add.add_argument("--type", dest="auth_type", choices=["oauth", "api-key", "api_key"], help="Credential type to add")
    auth_add.add_argument("--label", help="Optional display label")
    auth_add.add_argument("--api-key", help="API key value (otherwise prompted securely)")
    auth_add.add_argument("--portal-url", help="Nous portal base URL")
    auth_add.add_argument("--inference-url", help="Nous inference base URL")
    auth_add.add_argument("--client-id", help="OAuth client id")
    auth_add.add_argument("--scope", help="OAuth scope override")
    auth_add.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser for OAuth login")
    auth_add.add_argument("--timeout", type=float, help="OAuth/network timeout in seconds")
    auth_add.add_argument("--insecure", action="store_true", help="Disable TLS verification for OAuth login")
    auth_add.add_argument("--ca-bundle", help="Custom CA bundle for OAuth login")
    auth_list = auth_subparsers.add_parser("list", help="List pooled credentials")
    auth_list.add_argument("provider", nargs="?", help="Optional provider filter")
    auth_remove = auth_subparsers.add_parser("remove", help="Remove a pooled credential by index, id, or label")
    auth_remove.add_argument("provider", help="Provider id")
    auth_remove.add_argument("target", help="Credential index, entry id, or exact label")
    auth_reset = auth_subparsers.add_parser("reset", help="Clear exhaustion status for all credentials for a provider")
    auth_reset.add_argument("provider", help="Provider id")
    auth_parser.set_defaults(func=handlers['cmd_auth'])

    # =========================================================================
    # status command
    # =========================================================================
    status_parser = subparsers.add_parser(
        "status",
        help="Show status of all components",
        description="Display status of MimirAether components"
    )
    status_parser.add_argument(
        "--all",
        action="store_true",
        help="Show all details (redacted for sharing)"
    )
    status_parser.add_argument(
        "--deep",
        action="store_true",
        help="Run deep checks (may take longer)"
    )
    status_parser.set_defaults(func=handlers['cmd_status'])

    # =========================================================================
    # cron command
    # =========================================================================
    cron_parser = subparsers.add_parser(
        "cron",
        help="Cron job management",
        description="Manage scheduled tasks"
    )
    cron_subparsers = cron_parser.add_subparsers(dest="cron_command")

    # cron list
    cron_list = cron_subparsers.add_parser("list", help="List scheduled jobs")
    cron_list.add_argument("--all", action="store_true", help="Include disabled jobs")

    # cron create/add
    cron_create = cron_subparsers.add_parser("create", aliases=["add"], help="Create a scheduled job")
    cron_create.add_argument("schedule", help="Schedule like '30m', 'every 2h', or '0 9 * * *'")
    cron_create.add_argument("prompt", nargs="?", help="Optional self-contained prompt or task instruction")
    cron_create.add_argument("--name", help="Optional human-friendly job name")
    cron_create.add_argument("--deliver", help="Delivery target: origin, local, telegram, discord, signal, or platform:chat_id")
    cron_create.add_argument("--repeat", type=int, help="Optional repeat count")
    cron_create.add_argument("--skill", dest="skills", action="append", help="Attach a skill. Repeat to add multiple skills.")
    cron_create.add_argument("--script", help="Path to a Python script whose stdout is injected into the prompt each run")

    # cron edit
    cron_edit = cron_subparsers.add_parser("edit", help="Edit an existing scheduled job")
    cron_edit.add_argument("job_id", help="Job ID to edit")
    cron_edit.add_argument("--schedule", help="New schedule")
    cron_edit.add_argument("--prompt", help="New prompt/task instruction")
    cron_edit.add_argument("--name", help="New job name")
    cron_edit.add_argument("--deliver", help="New delivery target")
    cron_edit.add_argument("--repeat", type=int, help="New repeat count")
    cron_edit.add_argument("--skill", dest="skills", action="append", help="Replace the job's skills with this set. Repeat to attach multiple skills.")
    cron_edit.add_argument("--add-skill", dest="add_skills", action="append", help="Append a skill without replacing the existing list. Repeatable.")
    cron_edit.add_argument("--remove-skill", dest="remove_skills", action="append", help="Remove a specific attached skill. Repeatable.")
    cron_edit.add_argument("--clear-skills", action="store_true", help="Remove all attached skills from the job")
    cron_edit.add_argument("--script", help="Path to a Python script whose stdout is injected into the prompt each run. Pass empty string to clear.")

    # lifecycle actions
    cron_pause = cron_subparsers.add_parser("pause", help="Pause a scheduled job")
    cron_pause.add_argument("job_id", help="Job ID to pause")

    cron_resume = cron_subparsers.add_parser("resume", help="Resume a paused job")
    cron_resume.add_argument("job_id", help="Job ID to resume")

    cron_run = cron_subparsers.add_parser("run", help="Run a job on the next scheduler tick")
    cron_run.add_argument("job_id", help="Job ID to trigger")

    cron_remove = cron_subparsers.add_parser("remove", aliases=["rm", "delete"], help="Remove a scheduled job")
    cron_remove.add_argument("job_id", help="Job ID to remove")

    # cron status
    cron_subparsers.add_parser("status", help="Check if cron scheduler is running")

    # cron tick (mostly for debugging)
    cron_subparsers.add_parser("tick", help="Run due jobs once and exit")

    cron_parser.set_defaults(func=handlers['cmd_cron'])

    # =========================================================================
    # webhook command
    # =========================================================================
    webhook_parser = subparsers.add_parser(
        "webhook",
        help="Manage dynamic webhook subscriptions",
        description="Create, list, and remove webhook subscriptions for event-driven agent activation",
    )
    webhook_subparsers = webhook_parser.add_subparsers(dest="webhook_action")

    wh_sub = webhook_subparsers.add_parser("subscribe", aliases=["add"], help="Create a webhook subscription")
    wh_sub.add_argument("name", help="Route name (used in URL: /webhooks/<name>)")
    wh_sub.add_argument("--prompt", default="", help="Prompt template with {dot.notation} payload refs")
    wh_sub.add_argument("--events", default="", help="Comma-separated event types to accept")
    wh_sub.add_argument("--description", default="", help="What this subscription does")
    wh_sub.add_argument("--skills", default="", help="Comma-separated skill names to load")
    wh_sub.add_argument("--deliver", default="log", help="Delivery target: log, telegram, discord, slack, etc.")
    wh_sub.add_argument("--deliver-chat-id", default="", help="Target chat ID for cross-platform delivery")
    wh_sub.add_argument("--secret", default="", help="HMAC secret (auto-generated if omitted)")

    webhook_subparsers.add_parser("list", aliases=["ls"], help="List all dynamic subscriptions")

    wh_rm = webhook_subparsers.add_parser("remove", aliases=["rm"], help="Remove a subscription")
    wh_rm.add_argument("name", help="Subscription name to remove")

    wh_test = webhook_subparsers.add_parser("test", help="Send a test POST to a webhook route")
    wh_test.add_argument("name", help="Subscription name to test")
    wh_test.add_argument("--payload", default="", help="JSON payload to send (default: test payload)")

    webhook_parser.set_defaults(func=handlers['cmd_webhook'])

    # =========================================================================
    # doctor command
    # =========================================================================
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check configuration and dependencies",
        description="Diagnose issues with MimirAether setup"
    )
    doctor_parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix issues automatically"
    )
    doctor_parser.set_defaults(func=handlers['cmd_doctor'])

    # =========================================================================
    # dump command
    # =========================================================================
    dump_parser = subparsers.add_parser(
        "dump",
        help="Dump setup summary for support/debugging",
        description="Output a compact, plain-text summary of your MimirAether setup "
                    "that can be copy-pasted into Discord/GitHub for support context"
    )
    dump_parser.add_argument(
        "--show-keys",
        action="store_true",
        help="Show redacted API key prefixes (first/last 4 chars) instead of just set/not set"
    )
    dump_parser.set_defaults(func=handlers['cmd_dump'])

    # =========================================================================
    # debug command
    # =========================================================================
    debug_parser = subparsers.add_parser(
        "debug",
        help="Debug tools — upload logs and system info for support",
        description="Debug utilities for MimirAether. Use 'mimir debug share' to "
                    "upload a debug report (system info + recent logs) to a paste "
                    "service and get a shareable URL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
    Examples:
    mimir debug share              Upload debug report and print URL
    mimir debug share --lines 500  Include more log lines
    mimir debug share --expire 30  Keep paste for 30 days
    mimir debug share --local      Print report locally (no upload)
    """,
    )
    debug_sub = debug_parser.add_subparsers(dest="debug_command")
    share_parser = debug_sub.add_parser(
        "share",
        help="Upload debug report to a paste service and print a shareable URL",
    )
    share_parser.add_argument(
        "--lines", type=int, default=200,
        help="Number of log lines to include per log file (default: 200)",
    )
    share_parser.add_argument(
        "--expire", type=int, default=7,
        help="Paste expiry in days (default: 7)",
    )
    share_parser.add_argument(
        "--local", action="store_true",
        help="Print the report locally instead of uploading",
    )
    debug_parser.set_defaults(func=handlers['cmd_debug'])

    # =========================================================================
    # backup command
    # =========================================================================
    backup_parser = subparsers.add_parser(
        "backup",
        help="Back up MimirAether home directory to a zip file",
        description="Create a zip archive of your entire MimirAether configuration, "
                    "skills, sessions, and data (excludes the mimir-agent codebase). "
                    "Use --quick for a fast snapshot of just critical state files."
    )
    backup_parser.add_argument(
        "-o", "--output",
        help="Output path for the zip file (default: ~/mimir-backup-<timestamp>.zip)"
    )
    backup_parser.add_argument(
        "-q", "--quick",
        action="store_true",
        help="Quick snapshot: only critical state files (config, state.db, .env, auth, cron)"
    )
    backup_parser.add_argument(
        "-l", "--label",
        help="Label for the snapshot (only used with --quick)"
    )
    backup_parser.set_defaults(func=handlers['cmd_backup'])

    # =========================================================================
    # import command
    # =========================================================================
    import_parser = subparsers.add_parser(
        "import",
        help="Restore a MimirAether backup from a zip file",
        description="Extract a previously created MimirAether backup into your "
                    "MimirAether home directory, restoring configuration, skills, "
                    "sessions, and data"
    )
    import_parser.add_argument(
        "zipfile",
        help="Path to the backup zip file"
    )
    import_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files without confirmation"
    )
    import_parser.set_defaults(func=handlers['cmd_import'])

    # =========================================================================
    # config command
    # =========================================================================
    config_parser = subparsers.add_parser(
        "config",
        help="View and edit configuration",
        description="Manage MimirAether configuration"
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    # config show (default)
    config_subparsers.add_parser("show", help="Show current configuration")

    # config edit
    config_subparsers.add_parser("edit", help="Open config file in editor")

    # config set
    config_set = config_subparsers.add_parser("set", help="Set a configuration value")
    config_set.add_argument("key", nargs="?", help="Configuration key (e.g., model, terminal.backend)")
    config_set.add_argument("value", nargs="?", help="Value to set")

    # config path
    config_subparsers.add_parser("path", help="Print config file path")

    # config env-path
    config_subparsers.add_parser("env-path", help="Print .env file path")

    # config check
    config_subparsers.add_parser("check", help="Check for missing/outdated config")

    # config migrate
    config_subparsers.add_parser("migrate", help="Update config with new options")

    config_parser.set_defaults(func=handlers['cmd_config'])

    # =========================================================================
    # pairing command
    # =========================================================================
    pairing_parser = subparsers.add_parser(
        "pairing",
        help="Manage DM pairing codes for user authorization",
        description="Approve or revoke user access via pairing codes"
    )
    pairing_sub = pairing_parser.add_subparsers(dest="pairing_action")

    pairing_sub.add_parser("list", help="Show pending + approved users")

    pairing_approve_parser = pairing_sub.add_parser("approve", help="Approve a pairing code")
    pairing_approve_parser.add_argument("platform", help="Platform name (telegram, discord, slack, whatsapp)")
    pairing_approve_parser.add_argument("code", help="Pairing code to approve")

    pairing_revoke_parser = pairing_sub.add_parser("revoke", help="Revoke user access")
    pairing_revoke_parser.add_argument("platform", help="Platform name")
    pairing_revoke_parser.add_argument("user_id", help="User ID to revoke")

    pairing_sub.add_parser("clear-pending", help="Clear all pending codes")

    def cmd_pairing(args):
        from mimir_cli.pairing import pairing_command
        pairing_command(args)

    pairing_parser.set_defaults(func=cmd_pairing)

    # =========================================================================
    # skills command
    # =========================================================================
    skills_parser = subparsers.add_parser(
        "skills",
        help="Search, install, configure, and manage skills",
        description="Search, install, inspect, audit, configure, and manage skills from skills.sh, well-known agent skill endpoints, GitHub, ClawHub, and other registries."
    )
    skills_subparsers = skills_parser.add_subparsers(dest="skills_action")

    skills_browse = skills_subparsers.add_parser("browse", help="Browse all available skills (paginated)")
    skills_browse.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    skills_browse.add_argument("--size", type=int, default=20, help="Results per page (default: 20)")
    skills_browse.add_argument("--source", default="all",
                               choices=["all", "official", "skills-sh", "well-known", "github", "clawhub", "lobehub"],
                               help="Filter by source (default: all)")

    skills_search = skills_subparsers.add_parser("search", help="Search skill registries")
    skills_search.add_argument("query", help="Search query")
    skills_search.add_argument("--source", default="all", choices=["all", "official", "skills-sh", "well-known", "github", "clawhub", "lobehub"])
    skills_search.add_argument("--limit", type=int, default=10, help="Max results")

    skills_install = skills_subparsers.add_parser("install", help="Install a skill")
    skills_install.add_argument("identifier", help="Skill identifier (e.g. openai/skills/skill-creator)")
    skills_install.add_argument("--category", default="", help="Category folder to install into")
    skills_install.add_argument("--force", action="store_true", help="Install despite blocked scan verdict")
    skills_install.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt (needed in TUI mode)")

    skills_inspect = skills_subparsers.add_parser("inspect", help="Preview a skill without installing")
    skills_inspect.add_argument("identifier", help="Skill identifier")

    skills_list = skills_subparsers.add_parser("list", help="List installed skills")
    skills_list.add_argument("--source", default="all", choices=["all", "hub", "builtin", "local"])

    skills_check = skills_subparsers.add_parser("check", help="Check installed hub skills for updates")
    skills_check.add_argument("name", nargs="?", help="Specific skill to check (default: all)")

    skills_update = skills_subparsers.add_parser("update", help="Update installed hub skills")
    skills_update.add_argument("name", nargs="?", help="Specific skill to update (default: all outdated skills)")

    skills_audit = skills_subparsers.add_parser("audit", help="Re-scan installed hub skills")
    skills_audit.add_argument("name", nargs="?", help="Specific skill to audit (default: all)")

    skills_uninstall = skills_subparsers.add_parser("uninstall", help="Remove a hub-installed skill")
    skills_uninstall.add_argument("name", help="Skill name to remove")

    skills_publish = skills_subparsers.add_parser("publish", help="Publish a skill to a registry")
    skills_publish.add_argument("skill_path", help="Path to skill directory")
    skills_publish.add_argument("--to", default="github", choices=["github", "clawhub"], help="Target registry")
    skills_publish.add_argument("--repo", default="", help="Target GitHub repo (e.g. openai/skills)")

    skills_snapshot = skills_subparsers.add_parser("snapshot", help="Export/import skill configurations")
    snapshot_subparsers = skills_snapshot.add_subparsers(dest="snapshot_action")
    snap_export = snapshot_subparsers.add_parser("export", help="Export installed skills to a file")
    snap_export.add_argument("output", help="Output JSON file path (use - for stdout)")
    snap_import = snapshot_subparsers.add_parser("import", help="Import and install skills from a file")
    snap_import.add_argument("input", help="Input JSON file path")
    snap_import.add_argument("--force", action="store_true", help="Force install despite caution verdict")

    skills_tap = skills_subparsers.add_parser("tap", help="Manage skill sources")
    tap_subparsers = skills_tap.add_subparsers(dest="tap_action")
    tap_subparsers.add_parser("list", help="List configured taps")
    tap_add = tap_subparsers.add_parser("add", help="Add a GitHub repo as skill source")
    tap_add.add_argument("repo", help="GitHub repo (e.g. owner/repo)")
    tap_rm = tap_subparsers.add_parser("remove", help="Remove a tap")
    tap_rm.add_argument("name", help="Tap name to remove")

    # config sub-action: interactive enable/disable
    skills_subparsers.add_parser("config", help="Interactive skill configuration — enable/disable individual skills")

    def cmd_skills(args):
        # Route 'config' action to skills_config module
        if getattr(args, 'skills_action', None) == 'config':
            _require_tty("skills config")
            from mimir_cli.skills_config import skills_command as skills_config_command
            skills_config_command(args)
        else:
            from mimir_cli.skills_hub import skills_command
            skills_command(args)

    skills_parser.set_defaults(func=cmd_skills)
    return parser, subparsers
