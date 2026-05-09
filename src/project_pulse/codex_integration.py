from __future__ import annotations

import csv
import io
import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import ProjectPulseConfig
from .policy import MeaningfulChangeDetector
from .scanner import FilesystemScanner
from .session_tracker import SessionTracker


class CodexIntegrationError(RuntimeError):
    """Raised when Codex desktop integration cannot proceed safely."""


@dataclass(slots=True)
class CodexWatcherState:
    codex_running: bool
    last_seen_at: datetime | None = None
    last_recorded_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["last_seen_at"] = (
            self.last_seen_at.astimezone(UTC).isoformat()
            if self.last_seen_at
            else None
        )
        payload["last_recorded_at"] = (
            self.last_recorded_at.astimezone(UTC).isoformat()
            if self.last_recorded_at
            else None
        )
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CodexWatcherState:
        last_seen_at = payload.get("last_seen_at")
        last_recorded_at = payload.get("last_recorded_at")
        return cls(
            codex_running=bool(payload.get("codex_running", False)),
            last_seen_at=(
                datetime.fromisoformat(str(last_seen_at))
                if last_seen_at
                else None
            ),
            last_recorded_at=(
                datetime.fromisoformat(str(last_recorded_at))
                if last_recorded_at
                else None
            ),
        )


class CodexWatcher:
    STATE_STALE_MULTIPLIER = 3
    MIN_STATE_STALE_SECONDS = 60

    def __init__(
        self,
        config: ProjectPulseConfig,
        *,
        scanner: FilesystemScanner | None = None,
        detector: MeaningfulChangeDetector | None = None,
        tracker: SessionTracker | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config
        self.integration = config.data.codex_integration
        self.scanner = scanner or FilesystemScanner(config.data)
        self.detector = detector or MeaningfulChangeDetector(config.data)
        self.tracker = tracker or SessionTracker(config)
        self._sleep = sleep or time.sleep

    def record_open(self):
        if not self.integration.enabled:
            raise CodexIntegrationError(
                "Codex integration is disabled; set [codex_integration].enabled = true"
            )
        workspace_root = self._resolve_workspace_root()
        session = self.scanner.scan(watched_root=workspace_root)
        decision = self.detector.evaluate(session)
        return self.tracker.record(workspace_root, session, decision)

    def watch(self, *, max_polls: int | None = None) -> int:
        if not self.integration.enabled:
            raise CodexIntegrationError(
                "Codex integration is disabled; set [codex_integration].enabled = true"
            )
        if max_polls is not None and max_polls <= 0:
            return 0

        state = self._load_state()
        records_created = 0
        polls = 0
        while True:
            running = self._is_codex_running()
            now = datetime.now(UTC)
            state = self._normalize_state(state, now)

            if running and not state.codex_running:
                self.record_open()
                state.last_recorded_at = now
                records_created += 1

            state.codex_running = running
            state.last_seen_at = now
            self._save_state(state)

            polls += 1
            if max_polls is not None and polls >= max_polls:
                return records_created

            self._sleep(max(self.integration.poll_seconds, 1))

    def observe(self, running: bool) -> bool:
        """Test helper: feed one observed running state through the edge detector."""
        if not self.integration.enabled:
            raise CodexIntegrationError(
                "Codex integration is disabled; set [codex_integration].enabled = true"
            )

        state = self._load_state()
        now = datetime.now(UTC)
        state = self._normalize_state(state, now)
        recorded = False
        if running and not state.codex_running:
            self.record_open()
            state.last_recorded_at = now
            recorded = True
        state.codex_running = running
        state.last_seen_at = now
        self._save_state(state)
        return recorded

    def _resolve_workspace_root(self) -> Path:
        workspace_root = self.integration.workspace or self.config.data.watched_root
        workspace_root = workspace_root.resolve()
        watched_root = self.config.data.watched_root.resolve()
        try:
            workspace_root.relative_to(watched_root)
        except ValueError as error:
            raise CodexIntegrationError(
                "Codex integration workspace must live inside watched_root"
            ) from error
        if not workspace_root.exists():
            raise CodexIntegrationError(
                f"Codex integration workspace does not exist: {workspace_root}"
            )
        return workspace_root

    def _is_codex_running(self) -> bool:
        process_names = {
            name.lower()
            for name in self.integration.process_names
            if str(name).strip()
        }
        if not process_names:
            raise CodexIntegrationError(
                "Codex integration requires at least one process name"
            )
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise CodexIntegrationError(
                "could not inspect local Windows processes for Codex"
            ) from error

        rows = csv.reader(io.StringIO(result.stdout))
        return any(row and row[0].strip().lower() in process_names for row in rows)

    def _load_state(self) -> CodexWatcherState:
        state_path = self.integration.state_path
        if not state_path.exists():
            return CodexWatcherState(codex_running=False)
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CodexIntegrationError(
                f"Codex watcher state could not be read: {state_path}"
            ) from error
        if not isinstance(payload, dict):
            raise CodexIntegrationError(
                f"Codex watcher state has an invalid shape: {state_path}"
            )
        try:
            return CodexWatcherState.from_dict(payload)
        except ValueError as error:
            raise CodexIntegrationError(
                f"Codex watcher state contains invalid timestamps: {state_path}"
            ) from error

    def _save_state(self, state: CodexWatcherState) -> None:
        state_path = self.integration.state_path
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(state.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            raise CodexIntegrationError(
                f"Codex watcher state could not be written: {state_path}"
            ) from error

    def _normalize_state(
        self,
        state: CodexWatcherState,
        now: datetime,
    ) -> CodexWatcherState:
        if not state.codex_running or state.last_seen_at is None:
            return state

        stale_after = timedelta(
            seconds=max(
                self.integration.poll_seconds * self.STATE_STALE_MULTIPLIER,
                self.MIN_STATE_STALE_SECONDS,
            )
        )
        if (now - state.last_seen_at) <= stale_after:
            return state

        return CodexWatcherState(
            codex_running=False,
            last_seen_at=state.last_seen_at,
            last_recorded_at=state.last_recorded_at,
        )
