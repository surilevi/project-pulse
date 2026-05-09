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
