from __future__ import annotations

from pathlib import Path

from project_pulse.cli import build_parser


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
