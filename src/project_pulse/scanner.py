from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

from .models import (
    GitRepositorySnapshot,
    ProjectPulseConfigData,
    RecentFileActivity,
    WorkSession,
    WorkspaceSnapshot,
)


class FilesystemScanner:
    def __init__(self, config: ProjectPulseConfigData) -> None:
        self.config = config

    def scan(self, watched_root: Path | None = None) -> WorkSession:
        root = (watched_root or self.config.watched_root).resolve()
        observed_at = datetime.now(timezone.utc)
        workspace_roots = self._discover_workspace_roots(root)
        git_roots = self._discover_git_roots(root)
        recent_files = self._collect_recent_files(root, observed_at, workspace_roots, git_roots)
        workspaces = self._build_workspace_snapshots(workspace_roots, git_roots, recent_files)
        repositories = self._build_repository_snapshots(git_roots, recent_files, observed_at)
        latest_activity_at = max((item.modified_at for item in recent_files), default=None)
        session_started_at = min((item.modified_at for item in recent_files), default=None)
        recent_code_file_count = sum(
            1
            for item in recent_files
            if item.extension.lower() in self.config.high_signal_extensions
        )
        return WorkSession(
            watched_root=root,
            observed_at=observed_at,
            lookback_window=self.config.lookback_window,
            recent_files=recent_files,
            workspaces=workspaces,
            repositories=repositories,
            recent_code_file_count=recent_code_file_count,
            latest_activity_at=latest_activity_at,
            session_started_at=session_started_at,
        )

    def _discover_workspace_roots(self, root: Path) -> list[Path]:
        discovered: list[Path] = []
        marker_names = set(self.config.project_marker_names)
        for current_dir_text, dirnames, filenames in os.walk(root):
            current_dir = Path(current_dir_text)
            if marker_names.intersection(filenames) or ".git" in dirnames:
                discovered.append(current_dir.resolve())
            dirnames[:] = [
                name
                for name in dirnames
                if name not in self.config.ignored_directory_names
            ]
        return sorted(discovered, key=lambda item: len(str(item)), reverse=True)

    def _discover_git_roots(self, root: Path) -> list[Path]:
        discovered: list[Path] = []
        for current_dir_text, dirnames, _ in os.walk(root):
            current_dir = Path(current_dir_text)
            has_git_directory = ".git" in dirnames
            dirnames[:] = [
                name
                for name in dirnames
                if name not in self.config.ignored_directory_names
            ]
            if has_git_directory:
                discovered.append(current_dir.resolve())
        return sorted(discovered, key=lambda item: len(str(item)), reverse=True)

    def _collect_recent_files(
        self,
        root: Path,
        observed_at: datetime,
        workspace_roots: list[Path],
        git_roots: list[Path],
    ) -> list[RecentFileActivity]:
        cutoff = observed_at - self.config.lookback_window
        recent_files: list[RecentFileActivity] = []

        for current_dir_text, dirnames, filenames in os.walk(root):
            current_dir = Path(current_dir_text)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in self.config.ignored_directory_names
            ]
            for filename in filenames:
                if filename in self.config.ignored_file_names:
                    continue
                file_path = (current_dir / filename).resolve()
                try:
                    stat = file_path.stat()
                except OSError:
                    continue
                modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                if modified_at < cutoff:
                    continue
                workspace_root = self._match_root(file_path, workspace_roots)
                repository_root = self._match_repository(file_path, git_roots)
                recent_files.append(
                    RecentFileActivity(
                        path=file_path,
                        modified_at=modified_at,
                        extension=file_path.suffix.lower(),
                        workspace_root=workspace_root,
                        repository_root=repository_root,
                    )
                )

        recent_files.sort(key=lambda item: item.modified_at, reverse=True)
        return recent_files

    def _build_workspace_snapshots(
        self,
        workspace_roots: list[Path],
        git_roots: list[Path],
        recent_files: list[RecentFileActivity],
    ) -> list[WorkspaceSnapshot]:
        files_by_workspace: dict[Path, list[RecentFileActivity]] = defaultdict(list)
        for item in recent_files:
            if item.workspace_root is not None:
                files_by_workspace[item.workspace_root].append(item)

        snapshots: list[WorkspaceSnapshot] = []
        marker_names = set(self.config.project_marker_names)
        for workspace_root in workspace_roots:
            present_markers = tuple(
                sorted(
                    name
                    for name in marker_names
                    if (workspace_root / name).exists()
                )
            )
            snapshots.append(
                WorkspaceSnapshot(
                    root=workspace_root,
                    marker_names=present_markers,
                    repository_root=self._match_root(workspace_root, git_roots),
                    recent_file_count=len(files_by_workspace[workspace_root]),
                )
            )
        return snapshots

    def _build_repository_snapshots(
        self,
        git_roots: list[Path],
        recent_files: list[RecentFileActivity],
        observed_at: datetime,
    ) -> list[GitRepositorySnapshot]:
        files_by_repo: dict[Path, list[RecentFileActivity]] = defaultdict(list)
        for item in recent_files:
            if item.repository_root is not None:
                files_by_repo[item.repository_root].append(item)

        snapshots: list[GitRepositorySnapshot] = []
        for repo_root in git_roots:
            tracked_change_count, untracked_change_count = self._git_status_counts(repo_root)
            last_commit_at, last_commit_subject = self._git_last_commit(repo_root, observed_at)
            snapshots.append(
                GitRepositorySnapshot(
                    root=repo_root,
                    tracked_change_count=tracked_change_count,
                    untracked_change_count=untracked_change_count,
                    recent_file_count=len(files_by_repo[repo_root]),
                    last_commit_at=last_commit_at,
                    last_commit_subject=last_commit_subject,
                )
            )
        return snapshots

    def _git_status_counts(self, repo_root: Path) -> tuple[int, int]:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return 0, 0

        tracked = 0
        untracked = 0
        for line in result.stdout.splitlines():
            if line.startswith("??"):
                untracked += 1
            elif line.strip():
                tracked += 1
        return tracked, untracked

    def _git_last_commit(
        self,
        repo_root: Path,
        observed_at: datetime,
    ) -> tuple[datetime | None, str | None]:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), "log", "-1", "--format=%cI%x00%s"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None, None

        payload = result.stdout.strip()
        if not payload:
            return None, None

        committed_at_text, _, subject = payload.partition("\x00")
        try:
            committed_at = datetime.fromisoformat(committed_at_text)
        except ValueError:
            return None, None

        if committed_at.tzinfo is None:
            committed_at = committed_at.replace(tzinfo=timezone.utc)
        cutoff = observed_at - self.config.lookback_window
        if committed_at < cutoff:
            return None, None
        return committed_at, subject or None

    @staticmethod
    def _match_root(file_path: Path, roots: list[Path]) -> Path | None:
        for repo_root in roots:
            try:
                file_path.relative_to(repo_root)
            except ValueError:
                continue
            return repo_root
        return None

    @staticmethod
    def _match_repository(file_path: Path, git_roots: list[Path]) -> Path | None:
        return FilesystemScanner._match_root(file_path, git_roots)
