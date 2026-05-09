from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from .models import (
    PrivatePublisherConfig,
    ProjectPulseConfigData,
    ScoreWeights,
    SessionPersistenceConfig,
)

DEFAULT_CONFIG_NAME = "project-pulse.toml"
LOCAL_CONFIG_NAME = "project-pulse.local.toml"
EXAMPLE_CONFIG_NAME = "project-pulse.example.toml"
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
        data = ProjectPulseConfigData(
            watched_root=watched_root,
            lookback_window=timedelta(hours=int(raw.get("lookback_window_hours", 24))),
            minimum_recent_files=int(raw.get("minimum_recent_files", 4)),
            minimum_recent_code_files=int(raw.get("minimum_recent_code_files", 2)),
            minimum_workspaces_with_activity=int(raw.get("minimum_workspaces_with_activity", 1)),
            minimum_activity_score=int(raw.get("minimum_activity_score", 12)),
            maximum_reported_files=int(raw.get("maximum_reported_files", 12)),
            require_git_signal=bool(raw.get("require_git_signal", False)),
            expose_absolute_paths_in_reports=bool(
                raw.get("expose_absolute_paths_in_reports", False)
            ),
            high_signal_extensions=tuple(raw.get("high_signal_extensions", [])),
            ignored_directory_names=tuple(raw.get("ignored_directory_names", [])),
            low_signal_directory_names=tuple(raw.get("low_signal_directory_names", [])),
            ignored_file_names=tuple(raw.get("ignored_file_names", [])),
            project_marker_names=tuple(raw.get("project_marker_names", [])),
            weights=ScoreWeights(
                recent_file=int(weights.get("recent_file", 1)),
                recent_code_file=int(weights.get("recent_code_file", 3)),
                repository_with_uncommitted_changes=int(
                    weights.get("repository_with_uncommitted_changes", 4)
                ),
                repository_with_recent_commit=int(weights.get("repository_with_recent_commit", 5)),
            ),
            publisher=PrivatePublisherConfig(
                enabled=bool(publisher.get("enabled", False)),
                target_repo_path=target_repo_path,
                mirror_subdirectory=Path(publisher.get("mirror_subdirectory", ".")),
                commit_message_prefix=str(publisher.get("commit_message_prefix", "pulse")),
                push_after_commit=bool(publisher.get("push_after_commit", False)),
                require_explicit_push=bool(publisher.get("require_explicit_push", True)),
                exclude_globs=tuple(publisher.get("exclude_globs", [])),
            ),
            session_persistence=SessionPersistenceConfig(
                enabled=bool(session_persistence.get("enabled", True)),
                store_path=store_path,
                session_gap_minutes=int(session_persistence.get("session_gap_minutes", 90)),
                max_sessions_per_workspace=int(
                    session_persistence.get("max_sessions_per_workspace", 25)
                ),
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
    def load_public_audit_default(cls, base_directory: Path) -> ProjectPulseConfig:
        default_config = base_directory / DEFAULT_CONFIG_NAME
        if default_config.exists():
            return cls.load(default_config)
        example_config = base_directory / EXAMPLE_CONFIG_NAME
        if example_config.exists():
            return cls.load(example_config)
        return cls.from_text(DEFAULT_CONFIG_TEMPLATE, base_directory=base_directory)
