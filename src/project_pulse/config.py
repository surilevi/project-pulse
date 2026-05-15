from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TypeVar

from .models import (
    CodexIntegrationConfig,
    PrivatePublisherConfig,
    ProjectPulseConfigData,
    ScoreWeights,
    SessionPersistenceConfig,
)

DEFAULT_CONFIG_NAME = "project-pulse.toml"
LOCAL_CONFIG_NAME = "project-pulse.local.toml"
EXAMPLE_CONFIG_NAME = "project-pulse.example.toml"
T = TypeVar("T")
DEFAULT_CONFIG_TEMPLATE = """
watched_root = "."
lookback_window_hours = 24
minimum_recent_files = 4
minimum_recent_code_files = 2
minimum_workspaces_with_activity = 1
minimum_activity_score = 12
maximum_reported_files = 12
require_git_signal = false
expose_absolute_paths_in_reports = false

high_signal_extensions = [
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".rs",
  ".go",
  ".java",
  ".cs",
  ".sql",
  ".html",
  ".css",
  ".md",
  ".toml",
  ".yaml",
  ".yml",
]

ignored_directory_names = [
  ".git",
  ".idea",
  ".vscode",
  ".venv",
  "venv",
  "node_modules",
  "__pycache__",
  ".pytest_cache",
  ".ruff_cache",
  ".project-pulse-state",
  "dist",
  "build",
]

low_signal_directory_names = [
  "outputs",
]

ignored_file_names = [
  ".DS_Store",
  "Thumbs.db",
  "project-pulse.local.toml",
]

project_marker_names = [
  "pyproject.toml",
  "package.json",
  "requirements.txt",
  ".git",
]

[weights]
recent_file = 1
recent_code_file = 3
repository_with_uncommitted_changes = 4
repository_with_recent_commit = 5

[publisher]
enabled = false
target_repo_path = ""
mirror_subdirectory = "workspace"
commit_message_prefix = "pulse"
push_after_commit = false
require_explicit_push = true
exclude_globs = [
  ".git",
  ".git/**",
  ".env",
  ".env.*",
  "project-pulse.local.toml",
  "__pycache__/**",
  ".pytest_cache/**",
  ".ruff_cache/**",
  "dist/**",
  "build/**",
]

[session_persistence]
enabled = true
store_path = ".project-pulse-state/sessions.json"
session_gap_minutes = 90
max_sessions_per_workspace = 25

[codex_integration]
enabled = false
workspace = ""
process_names = ["Codex.exe", "codex.exe"]
poll_seconds = 20
state_path = ".project-pulse-state/codex-watcher-state.json"
""".strip()


@dataclass(slots=True)
class ProjectPulseConfig:
    data: ProjectPulseConfigData

    @classmethod
    def load(cls, config_path: Path) -> ProjectPulseConfig:
        return cls.from_text(
            config_path.read_text(encoding="utf-8"),
            base_directory=config_path.resolve().parent,
        )

    @classmethod
    def from_text(
        cls,
        raw_text: str,
        base_directory: Path | None = None,
    ) -> ProjectPulseConfig:
        raw = tomllib.loads(raw_text)
        weights = raw.get("weights", {})
        publisher = raw.get("publisher", {})
        session_persistence = raw.get("session_persistence", {})
        codex_integration = raw.get("codex_integration", {})
        watched_root = Path(raw.get("watched_root", ".")).expanduser()
        if base_directory is not None and not watched_root.is_absolute():
            watched_root = (base_directory / watched_root).resolve()
        target_repo_path_text = str(publisher.get("target_repo_path", "")).strip()
        target_repo_path: Path | None = None
        if target_repo_path_text:
            target_repo_path = Path(target_repo_path_text).expanduser()
            if base_directory is not None and not target_repo_path.is_absolute():
                target_repo_path = (base_directory / target_repo_path).resolve()
        store_path = Path(
            session_persistence.get("store_path", ".project-pulse-state/sessions.json")
        ).expanduser()
        if base_directory is not None and not store_path.is_absolute():
            store_path = (base_directory / store_path).resolve()
        codex_workspace_text = str(codex_integration.get("workspace", "")).strip()
        codex_workspace: Path | None = None
        if codex_workspace_text:
            codex_workspace = Path(codex_workspace_text).expanduser()
            if not codex_workspace.is_absolute():
                codex_workspace = (watched_root / codex_workspace).resolve()
        codex_state_path = Path(
            codex_integration.get(
                "state_path",
                ".project-pulse-state/codex-watcher-state.json",
            )
        ).expanduser()
        if base_directory is not None and not codex_state_path.is_absolute():
            codex_state_path = (base_directory / codex_state_path).resolve()
        data = ProjectPulseConfigData(
            watched_root=watched_root,
            lookback_window=timedelta(
                hours=_get_int(raw, "lookback_window_hours", 24)
            ),
            minimum_recent_files=_get_int(raw, "minimum_recent_files", 4),
            minimum_recent_code_files=_get_int(raw, "minimum_recent_code_files", 2),
            minimum_workspaces_with_activity=_get_int(
                raw,
                "minimum_workspaces_with_activity",
                1,
            ),
            minimum_activity_score=_get_int(raw, "minimum_activity_score", 12),
            maximum_reported_files=_get_int(raw, "maximum_reported_files", 12),
            require_git_signal=_get_bool(raw, "require_git_signal", False),
            expose_absolute_paths_in_reports=_get_bool(
                raw,
                "expose_absolute_paths_in_reports",
                False,
            ),
            high_signal_extensions=_get_str_tuple(raw, "high_signal_extensions", ()),
            ignored_directory_names=_get_str_tuple(raw, "ignored_directory_names", ()),
            low_signal_directory_names=_get_str_tuple(raw, "low_signal_directory_names", ()),
            ignored_file_names=_get_str_tuple(raw, "ignored_file_names", ()),
            project_marker_names=_get_str_tuple(raw, "project_marker_names", ()),
            weights=ScoreWeights(
                recent_file=_get_int(weights, "recent_file", 1, section="weights"),
                recent_code_file=_get_int(weights, "recent_code_file", 3, section="weights"),
                repository_with_uncommitted_changes=_get_int(
                    weights,
                    "repository_with_uncommitted_changes",
                    4,
                    section="weights",
                ),
                repository_with_recent_commit=_get_int(
                    weights,
                    "repository_with_recent_commit",
                    5,
                    section="weights",
                ),
            ),
            publisher=PrivatePublisherConfig(
                enabled=_get_bool(publisher, "enabled", False, section="publisher"),
                target_repo_path=target_repo_path,
                mirror_subdirectory=Path(publisher.get("mirror_subdirectory", ".")),
                commit_message_prefix=str(publisher.get("commit_message_prefix", "pulse")),
                push_after_commit=_get_bool(
                    publisher,
                    "push_after_commit",
                    False,
                    section="publisher",
                ),
                require_explicit_push=_get_bool(
                    publisher,
                    "require_explicit_push",
                    True,
                    section="publisher",
                ),
                exclude_globs=_get_str_tuple(publisher, "exclude_globs", (), section="publisher"),
            ),
            session_persistence=SessionPersistenceConfig(
                enabled=_get_bool(
                    session_persistence,
                    "enabled",
                    True,
                    section="session_persistence",
                ),
                store_path=store_path,
                session_gap_minutes=_get_int(
                    session_persistence,
                    "session_gap_minutes",
                    90,
                    section="session_persistence",
                ),
                max_sessions_per_workspace=_get_int(
                    session_persistence,
                    "max_sessions_per_workspace",
                    25,
                    section="session_persistence",
                ),
            ),
            codex_integration=CodexIntegrationConfig(
                enabled=_get_bool(
                    codex_integration,
                    "enabled",
                    False,
                    section="codex_integration",
                ),
                workspace=codex_workspace,
                process_names=_get_str_tuple(
                    codex_integration,
                    "process_names",
                    (),
                    section="codex_integration",
                ),
                poll_seconds=_get_int(
                    codex_integration,
                    "poll_seconds",
                    20,
                    section="codex_integration",
                ),
                state_path=codex_state_path,
            ),
        )
        return cls(data=data)

    @classmethod
    def load_default(cls, base_directory: Path) -> ProjectPulseConfig:
        local_config = base_directory / LOCAL_CONFIG_NAME
        if local_config.exists():
            return cls.load(local_config)
        default_config = base_directory / DEFAULT_CONFIG_NAME
        if default_config.exists():
            return cls.load(default_config)
        example_config = base_directory / EXAMPLE_CONFIG_NAME
        if example_config.exists():
            return cls.load(example_config)
        return cls.from_text(DEFAULT_CONFIG_TEMPLATE, base_directory=base_directory)

    @classmethod
    def load_safety_audit_default(cls, base_directory: Path) -> ProjectPulseConfig:
        default_config = base_directory / DEFAULT_CONFIG_NAME
        if default_config.exists():
            return cls.load(default_config)
        example_config = base_directory / EXAMPLE_CONFIG_NAME
        if example_config.exists():
            return cls.load(example_config)
        return cls.from_text(DEFAULT_CONFIG_TEMPLATE, base_directory=base_directory)


def _setting_name(key: str, section: str | None) -> str:
    return f"{section}.{key}" if section else key


def _get_typed(
    values: dict[str, object],
    key: str,
    default: T,
    expected_type: type | tuple[type, ...],
    *,
    section: str | None = None,
    validator: Callable[[object], bool] | None = None,
) -> T:
    value = values.get(key, default)
    if not isinstance(value, expected_type) or (validator is not None and not validator(value)):
        expected = (
            "a list of strings"
            if validator is _is_str_list
            else expected_type.__name__
            if isinstance(expected_type, type)
            else " or ".join(item.__name__ for item in expected_type)
        )
        raise ValueError(f"{_setting_name(key, section)} must be {expected}")
    return value


def _get_bool(
    values: dict[str, object],
    key: str,
    default: bool,
    *,
    section: str | None = None,
) -> bool:
    return _get_typed(values, key, default, bool, section=section)


def _get_int(
    values: dict[str, object],
    key: str,
    default: int,
    *,
    section: str | None = None,
) -> int:
    return _get_typed(
        values,
        key,
        default,
        int,
        section=section,
        validator=lambda value: not isinstance(value, bool),
    )


def _get_str_tuple(
    values: dict[str, object],
    key: str,
    default: tuple[str, ...],
    *,
    section: str | None = None,
) -> tuple[str, ...]:
    value = _get_typed(
        values,
        key,
        list(default),
        list,
        section=section,
        validator=_is_str_list,
    )
    return tuple(value)


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
