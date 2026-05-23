"""E-004: mimir_cli.config.CLI_CONFIG defaults for clarify/approval paths."""


def test_cli_config_import_and_keys():
    from mimir_cli.config import CLI_CONFIG

    assert isinstance(CLI_CONFIG, dict)
    assert CLI_CONFIG["clarify"]["timeout"] == 120
    assert CLI_CONFIG["approvals"]["timeout"] == 60


def test_callbacks_clarify_config_lookup_no_cli_import():
    from mimir_cli.config import CLI_CONFIG

    timeout = CLI_CONFIG.get("clarify", {}).get("timeout", 120)
    assert timeout == 120
