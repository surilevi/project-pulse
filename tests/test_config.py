from __future__ import annotations

from pathlib import Path

import pytest

from project_pulse.config import ProjectPulseConfig


def test_relative_watched_root_resolves_against_config_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    project_dir = config_dir / "workspace"
    project_dir.mkdir()
    config_path = config_dir / "project-pulse.toml"
    config_path.write_text(
        """
watched_root = "workspace"
lookback_window_hours = 24
minimum_recent_files = 4
minimum_recent_code_files = 2
minimum_workspaces_with_activity = 1
minimum_activity_score = 12
maximum_reported_files = 12
require_git_signal = false
expose_absolute_paths_in_reports = false
high_signal_extensions = [".py"]
ignored_directory_names = [".git"]
low_signal_directory_names = []
ignored_file_names = []
project_marker_names = ["pyproject.toml"]
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
exclude_globs = []
""".strip(),
        encoding="utf-8",
    )

    config = ProjectPulseConfig.load(config_path)

    assert config.data.watched_root == project_dir.resolve()


def test_config_rejects_string_boolean() -> None:
    with pytest.raises(ValueError, match="require_git_signal must be bool"):
        ProjectPulseConfig.from_text(
            """
watched_root = "."
require_git_signal = "false"
""".strip()
        )


def test_config_rejects_non_string_list_values() -> None:
    with pytest.raises(ValueError, match="ignored_directory_names must be a list of strings"):
        ProjectPulseConfig.from_text(
            """
watched_root = "."
ignored_directory_names = [".git", 123]
""".strip()
        )
