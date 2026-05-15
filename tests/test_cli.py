from __future__ import annotations

from pathlib import Path

import pytest

from project_pulse.cli import build_parser, main


def test_config_works_before_subcommand() -> None:
    args = build_parser().parse_args(["--config", "example.toml", "scan"])
    assert args.command == "scan"
    assert args.config == Path("example.toml")


def test_config_works_after_subcommand() -> None:
    args = build_parser().parse_args(["scan", "--config", "example.toml"])
    assert args.command == "scan"
    assert args.config == Path("example.toml")


def test_codex_watch_parser_accepts_max_polls() -> None:
    args = build_parser().parse_args(["codex-watch", "--max-polls", "2"])
    assert args.command == "codex-watch"
    assert args.max_polls == 2


def test_safety_audit_is_primary_audit_command() -> None:
    args = build_parser().parse_args(["safety-audit"])
    assert args.command == "safety-audit"


def test_legacy_audit_alias_maps_to_safety_audit() -> None:
    args = build_parser().parse_args(["public-audit"])
    assert args.command == "safety-audit"


def test_invalid_config_reports_clean_cli_error(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "project-pulse.toml"
    config_path.write_text(
        """
watched_root = "."
require_git_signal = "false"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as raised:
        main(["--config", str(config_path), "scan"])

    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert "project-pulse: invalid config: require_git_signal must be bool" in captured.err
