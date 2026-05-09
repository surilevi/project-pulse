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
class PrivatePublisherConfig:
    enabled: bool
    target_repo_path: Path | None
    mirror_subdirectory: Path
    commit_message_prefix: str
    push_after_commit: bool
    require_explicit_push: bool
    exclude_globs: tuple[str, ...]


@dataclass(slots=True)
class SessionPersistenceConfig:
    enabled: bool
    store_path: Path
    session_gap_minutes: int
    max_sessions_per_workspace: int


@dataclass(slots=True)
class CodexIntegrationConfig:
    enabled: bool
    workspace: Path | None
    process_names: tuple[str, ...]
    poll_seconds: int
    state_path: Path


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
    low_signal_directory_names: tuple[str, ...]
    ignored_file_names: tuple[str, ...]
    project_marker_names: tuple[str, ...]
    weights: ScoreWeights
    publisher: PrivatePublisherConfig
    session_persistence: SessionPersistenceConfig
    codex_integration: CodexIntegrationConfig


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


@dataclass(slots=True)
class PrivatePublishResult:
    workspace_root: Path
    target_repo_path: Path
    mirror_path: Path
    branch: str
    commit_created: bool
    commit_sha: str | None
    pushed: bool
    commit_message: str | None
    changed_files: list[str]
    metadata_path: Path


@dataclass(slots=True)
class PersistedSession:
    session_id: str
    workspace_root: Path
    workspace_name: str
    started_at: datetime
    updated_at: datetime
    latest_activity_at: datetime | None
    last_observed_at: datetime
    record_count: int
    recent_file_count: int
    recent_code_file_count: int
    workspaces_with_activity: int
    repositories_with_uncommitted_changes: int
    repositories_with_recent_commits: int
    activity_score: int
    publishable: bool
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["workspace_root"] = str(self.workspace_root)
        payload["started_at"] = self.started_at.isoformat()
        payload["updated_at"] = self.updated_at.isoformat()
        payload["latest_activity_at"] = (
            self.latest_activity_at.isoformat() if self.latest_activity_at else None
        )
        payload["last_observed_at"] = self.last_observed_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PersistedSession:
        latest_activity_at = payload.get("latest_activity_at")
        return cls(
            session_id=str(payload["session_id"]),
            workspace_root=Path(str(payload["workspace_root"])),
            workspace_name=str(payload["workspace_name"]),
            started_at=datetime.fromisoformat(str(payload["started_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            latest_activity_at=(
                datetime.fromisoformat(str(latest_activity_at))
                if latest_activity_at
                else None
            ),
            last_observed_at=datetime.fromisoformat(str(payload["last_observed_at"])),
            record_count=int(payload["record_count"]),
            recent_file_count=int(payload["recent_file_count"]),
            recent_code_file_count=int(payload["recent_code_file_count"]),
            workspaces_with_activity=int(payload["workspaces_with_activity"]),
            repositories_with_uncommitted_changes=int(
                payload["repositories_with_uncommitted_changes"]
            ),
            repositories_with_recent_commits=int(payload["repositories_with_recent_commits"]),
            activity_score=int(payload["activity_score"]),
            publishable=bool(payload["publishable"]),
            reasons=[str(item) for item in payload.get("reasons", [])],
            blockers=[str(item) for item in payload.get("blockers", [])],
        )


@dataclass(slots=True)
class SessionRecordResult:
    session: PersistedSession
    created: bool
    store_path: Path
