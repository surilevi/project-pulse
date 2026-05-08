from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import tomllib

from .models import ProjectPulseConfigData, ScoreWeights


DEFAULT_CONFIG_NAME = "project-pulse.toml"
LOCAL_CONFIG_NAME = "project-pulse.local.toml"
EXAMPLE_CONFIG_NAME = "project-pulse.example.toml"


@dataclass(slots=True)
class ProjectPulseConfig:
    data: ProjectPulseConfigData

    @classmethod
    def load(cls, config_path: Path) -> "ProjectPulseConfig":
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        weights = raw["weights"]
        data = ProjectPulseConfigData(
            watched_root=Path(raw["watched_root"]).expanduser(),
            lookback_window=timedelta(hours=int(raw["lookback_window_hours"])),
            minimum_recent_files=int(raw["minimum_recent_files"]),
            minimum_recent_code_files=int(raw["minimum_recent_code_files"]),
            minimum_workspaces_with_activity=int(raw["minimum_workspaces_with_activity"]),
            minimum_activity_score=int(raw["minimum_activity_score"]),
            maximum_reported_files=int(raw["maximum_reported_files"]),
            require_git_signal=bool(raw["require_git_signal"]),
            expose_absolute_paths_in_reports=bool(raw["expose_absolute_paths_in_reports"]),
            high_signal_extensions=tuple(raw["high_signal_extensions"]),
            ignored_directory_names=tuple(raw["ignored_directory_names"]),
            ignored_file_names=tuple(raw["ignored_file_names"]),
            project_marker_names=tuple(raw["project_marker_names"]),
            weights=ScoreWeights(
                recent_file=int(weights["recent_file"]),
                recent_code_file=int(weights["recent_code_file"]),
                repository_with_uncommitted_changes=int(
                    weights["repository_with_uncommitted_changes"]
                ),
                repository_with_recent_commit=int(weights["repository_with_recent_commit"]),
            ),
        )
        return cls(data=data)

    @classmethod
    def load_default(cls, base_directory: Path) -> "ProjectPulseConfig":
        local_config = base_directory / LOCAL_CONFIG_NAME
        if local_config.exists():
            return cls.load(local_config)
        example_config = base_directory / EXAMPLE_CONFIG_NAME
        return cls.load(example_config)
