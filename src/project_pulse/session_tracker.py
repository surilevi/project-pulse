from __future__ import annotations

import json
from datetime import timedelta
from hashlib import sha1
from pathlib import Path

from .config import ProjectPulseConfig
from .models import PersistedSession, PublishDecision, SessionRecordResult, WorkSession


class SessionTrackerError(RuntimeError):
    """Raised when session persistence cannot proceed safely."""


class SessionTracker:
    def __init__(self, config: ProjectPulseConfig) -> None:
        self.config = config
        self.persistence = config.data.session_persistence

    def record(
        self,
        workspace_root: Path,
        session: WorkSession,
        decision: PublishDecision,
    ) -> SessionRecordResult:
        if not self.persistence.enabled:
            raise SessionTrackerError(
                "session persistence is disabled in config; "
                "set [session_persistence].enabled = true"
            )

        workspace_root = workspace_root.resolve()
        watched_root = self.config.data.watched_root.resolve()
        try:
            workspace_root.relative_to(watched_root)
        except ValueError as error:
            raise SessionTrackerError(
                "workspace must live inside the configured watched_root"
            ) from error
        self._ensure_safe_store_path(watched_root)

        sessions = self._load_sessions()
        workspace_key = self._workspace_key(workspace_root, watched_root)
        workspace_sessions = sessions.get(workspace_key, [])
        persisted = [PersistedSession.from_dict(item) for item in workspace_sessions]
        latest = persisted[-1] if persisted else None

        gap = timedelta(minutes=self.persistence.session_gap_minutes)
        if latest is None or self._starts_new_session(latest, session, gap):
            active = self._new_session(workspace_root, session, decision)
            created = True
            persisted.append(active)
        else:
            active = self._update_session(latest, session, decision)
            persisted[-1] = active
            created = False

        max_sessions = self.persistence.max_sessions_per_workspace
        if max_sessions > 0:
            persisted = persisted[-max_sessions:]

        sessions[workspace_key] = [item.to_dict() for item in persisted]
        self._save_sessions(sessions)
        return SessionRecordResult(
            session=active,
            created=created,
            store_path=self.persistence.store_path,
        )

    def list_sessions(self, workspace_root: Path | None = None) -> list[PersistedSession]:
        sessions = self._load_sessions()
        if workspace_root is None:
            flattened: list[PersistedSession] = []
            for items in sessions.values():
                flattened.extend(PersistedSession.from_dict(item) for item in items)
            return sorted(flattened, key=lambda item: item.updated_at, reverse=True)

        workspace_key = self._workspace_key(
            workspace_root.resolve(),
            self.config.data.watched_root.resolve(),
        )
        return [
            PersistedSession.from_dict(item)
            for item in sessions.get(workspace_key, [])
        ]

    def _new_session(
        self,
        workspace_root: Path,
        session: WorkSession,
        decision: PublishDecision,
    ) -> PersistedSession:
        started_at = session.session_started_at or session.observed_at
        timestamp_seed = (
            f"{workspace_root}:{started_at.isoformat()}:"
            f"{session.observed_at.isoformat()}"
        )
        session_id = sha1(timestamp_seed.encode("utf-8")).hexdigest()[:12]
        relative_workspace_root = Path(
            self._relative_to_watched_root(
                workspace_root,
                self.config.data.watched_root.resolve(),
            )
        )
        return PersistedSession(
            session_id=session_id,
            workspace_root=relative_workspace_root,
            workspace_name=workspace_root.name,
            started_at=started_at,
            updated_at=session.observed_at,
            latest_activity_at=session.latest_activity_at,
            last_observed_at=session.observed_at,
            record_count=1,
            recent_file_count=session.recent_file_count,
            recent_code_file_count=session.recent_code_file_count,
            workspaces_with_activity=session.workspaces_with_activity,
            repositories_with_uncommitted_changes=int(
                decision.metrics.get("repositories_with_uncommitted_changes", 0)
            ),
            repositories_with_recent_commits=int(
                decision.metrics.get("repositories_with_recent_commits", 0)
            ),
            activity_score=decision.score,
            publishable=decision.publishable,
            reasons=list(decision.reasons),
            blockers=list(decision.blockers),
        )

    def _update_session(
        self,
        existing: PersistedSession,
        session: WorkSession,
        decision: PublishDecision,
    ) -> PersistedSession:
        latest_activity_at = existing.latest_activity_at
        if session.latest_activity_at and (
            latest_activity_at is None or session.latest_activity_at > latest_activity_at
        ):
            latest_activity_at = session.latest_activity_at

        return PersistedSession(
            session_id=existing.session_id,
            workspace_root=existing.workspace_root,
            workspace_name=existing.workspace_name,
            started_at=existing.started_at,
            updated_at=session.observed_at,
            latest_activity_at=latest_activity_at,
            last_observed_at=session.observed_at,
            record_count=existing.record_count + 1,
            recent_file_count=session.recent_file_count,
            recent_code_file_count=session.recent_code_file_count,
            workspaces_with_activity=session.workspaces_with_activity,
            repositories_with_uncommitted_changes=int(
                decision.metrics.get("repositories_with_uncommitted_changes", 0)
            ),
            repositories_with_recent_commits=int(
                decision.metrics.get("repositories_with_recent_commits", 0)
            ),
            activity_score=decision.score,
            publishable=decision.publishable,
            reasons=list(decision.reasons),
            blockers=list(decision.blockers),
        )

    def _load_sessions(self) -> dict[str, list[dict[str, object]]]:
        store_path = self.persistence.store_path
        if not store_path.exists():
            return {}
        try:
            payload = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SessionTrackerError(
                f"session store could not be read as valid JSON: {store_path}"
            ) from error
        if not isinstance(payload, dict):
            raise SessionTrackerError(
                f"session store must contain a JSON object at the top level: {store_path}"
            )
        validated: dict[str, list[dict[str, object]]] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, list):
                raise SessionTrackerError(
                    f"session store has an invalid workspace entry: {store_path}"
                )
            validated[key] = []
            for item in value:
                if not isinstance(item, dict):
                    raise SessionTrackerError(
                        f"session store contains a non-object session record: {store_path}"
                    )
                validated[key].append(item)
        return validated

    def _save_sessions(self, sessions: dict[str, list[dict[str, object]]]) -> None:
        store_path = self.persistence.store_path
        try:
            store_path.parent.mkdir(parents=True, exist_ok=True)
            store_path.write_text(json.dumps(sessions, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            raise SessionTrackerError(
                f"session store could not be written: {store_path}"
            ) from error

    def _workspace_key(self, workspace_root: Path, watched_root: Path) -> str:
        return self._relative_to_watched_root(workspace_root, watched_root)

    def _relative_to_watched_root(self, workspace_root: Path, watched_root: Path) -> str:
        return workspace_root.relative_to(watched_root).as_posix()

    def _ensure_safe_store_path(self, watched_root: Path) -> None:
        store_path = self.persistence.store_path.resolve()
        try:
            relative_to_root = store_path.relative_to(watched_root)
        except ValueError:
            return
        if ".project-pulse-state" not in relative_to_root.parts:
            raise SessionTrackerError(
                "session store path must live outside watched_root or inside "
                "a .project-pulse-state directory"
            )

    def _starts_new_session(
        self,
        latest: PersistedSession,
        session: WorkSession,
        gap: timedelta,
    ) -> bool:
        previous_activity_at = latest.latest_activity_at or latest.last_observed_at
        current_activity_at = session.session_started_at or session.observed_at
        return (current_activity_at - previous_activity_at) > gap
