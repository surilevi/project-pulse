from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(slots=True)
class ScoreWeights:
    recent_file: int
    recent_code_file: int
    repository_with_uncommitted_changes: int
    repository_with_recent_commit: int


@dataclass(slots=True)
class ProjectPulseConfigData:
    watched_root: Path
    lookback_window: timedelta
    minimum_recent_files: int
    minimum_recent_code_files: int
    minimum_workspaces_with_activity: int
    minimum_activity_score: int
    maximum_reported_files: int
    require_git_signal: bool
    expose_absolute_paths_in_reports: bool
    high_signal_extensions: tuple[str, ...]
    ignored_directory_names: tuple[str, ...]
    ignored_file_names: tuple[str, ...]
    project_marker_names: tuple[str, ...]
    weights: ScoreWeights


@dataclass(slots=True)
class RecentFileActivity:
    path: Path
    modified_at: datetime
    extension: str
    workspace_root: Path | None
    repository_root: Path | None

    @property
    def is_code_like(self) -> bool:
        return bool(self.extension)


@dataclass(slots=True)
class WorkspaceSnapshot:
    root: Path
    marker_names: tuple[str, ...]
    repository_root: Path | None
    recent_file_count: int


@dataclass(slots=True)
class GitRepositorySnapshot:
    root: Path
    tracked_change_count: int
    untracked_change_count: int
    recent_file_count: int
    last_commit_at: datetime | None = None
    last_commit_subject: str | None = None

    @property
    def has_uncommitted_changes(self) -> bool:
        return (self.tracked_change_count + self.untracked_change_count) > 0

    @property
    def has_recent_commit(self) -> bool:
        return self.last_commit_at is not None


@dataclass(slots=True)
class WorkSession:
    watched_root: Path
    observed_at: datetime
    lookback_window: timedelta
    recent_files: list[RecentFileActivity]
    workspaces: list[WorkspaceSnapshot]
    repositories: list[GitRepositorySnapshot]
    recent_code_file_count: int
    latest_activity_at: datetime | None
    session_started_at: datetime | None

    @property
    def recent_file_count(self) -> int:
        return len(self.recent_files)

    @property
    def workspaces_with_activity(self) -> int:
        return sum(1 for workspace in self.workspaces if workspace.recent_file_count > 0)


@dataclass(slots=True)
class PublishDecision:
    publishable: bool
    score: int
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    metrics: dict[str, int | str | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
