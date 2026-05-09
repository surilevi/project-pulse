from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .config import ProjectPulseConfig
from .models import PrivatePublishResult, PublishDecision, WorkSession

METADATA_RELATIVE_PATH = Path(".project-pulse") / "private-publish.json"


class PrivatePublisherError(RuntimeError):
    """Raised when private publishing cannot proceed safely."""


class PrivateRepoPublisher:
    def __init__(self, config: ProjectPulseConfig) -> None:
        self.config = config
        self.publisher = config.data.publisher

    def publish(
        self,
        workspace_root: Path,
        session: WorkSession,
        decision: PublishDecision,
        *,
        push: bool = False,
        branch: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> PrivatePublishResult:
        if not self.publisher.enabled:
            raise PrivatePublisherError(
                "private publishing is disabled in config; set [publisher].enabled = true"
            )
        if self.publisher.target_repo_path is None:
            raise PrivatePublisherError(
                "private publisher target_repo_path is not configured"
            )
        if not force and not decision.publishable:
            raise PrivatePublisherError(
                "session is not publishable; rerun with --force if you want to override policy"
            )

        workspace_root = workspace_root.resolve()
        watched_root = self.config.data.watched_root.resolve()
        self._ensure_within_watched_root(workspace_root, watched_root)

        target_repo = self.publisher.target_repo_path.resolve()
        self._ensure_git_repo(target_repo)
        self._ensure_distinct_paths(workspace_root, target_repo)
        self._ensure_clean_target_repo(target_repo)

        mirror_subdirectory = self.publisher.mirror_subdirectory
        if mirror_subdirectory.is_absolute():
            raise PrivatePublisherError("publisher mirror_subdirectory must be relative")

        if branch:
            self._switch_branch(target_repo, branch)
        active_branch = branch or self._current_branch(target_repo)

        mirror_path = (target_repo / mirror_subdirectory).resolve()
        try:
            mirror_path.relative_to(target_repo)
        except ValueError as error:
            raise PrivatePublisherError(
                "publisher mirror_subdirectory must stay inside the target private repo"
            ) from error
        mirror_path.mkdir(parents=True, exist_ok=True)

        desired_files = self._collect_publishable_files(workspace_root)
        self._sync_workspace(workspace_root, mirror_path, desired_files)
        metadata_path = (target_repo / METADATA_RELATIVE_PATH).resolve()
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps(
                self._build_metadata_payload(workspace_root, session, decision, desired_files),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        changed_files = self._changed_files(target_repo)
        commit_created = False
        commit_sha: str | None = None
        pushed = False
        commit_message = message or self._default_commit_message(workspace_root)

        if changed_files:
            self._stage_managed_paths(target_repo, mirror_subdirectory, METADATA_RELATIVE_PATH)
            self._git(target_repo, "commit", "-m", commit_message)
            commit_created = True
            commit_sha = self._git(target_repo, "rev-parse", "HEAD").stdout.strip()
            if self._should_push(push):
                self._ensure_remote_exists(target_repo)
                self._git(target_repo, "push", "-u", "origin", active_branch)
                pushed = True

        return PrivatePublishResult(
            workspace_root=workspace_root,
            target_repo_path=target_repo,
            mirror_path=mirror_path,
            branch=active_branch,
            commit_created=commit_created,
            commit_sha=commit_sha,
            pushed=pushed,
            commit_message=commit_message if commit_created else None,
            changed_files=changed_files,
            metadata_path=metadata_path,
        )

    def _collect_publishable_files(self, workspace_root: Path) -> set[Path]:
        desired_files: set[Path] = set()
        ignored_dirs = set(self.config.data.ignored_directory_names)
        low_signal_dirs = set(self.config.data.low_signal_directory_names)
        ignored_files = set(self.config.data.ignored_file_names)

        for current_dir_text, dirnames, filenames in os.walk(workspace_root):
            current_dir = Path(current_dir_text)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in ignored_dirs and name not in low_signal_dirs
            ]
            for filename in filenames:
                if filename == ".git" or filename in ignored_files:
                    continue
                file_path = (current_dir / filename).resolve()
                relative_path = file_path.relative_to(workspace_root)
                if self._matches_exclude(relative_path):
                    continue
                desired_files.add(relative_path)
        return desired_files

    def _sync_workspace(
        self,
        workspace_root: Path,
        mirror_path: Path,
        desired_files: set[Path],
    ) -> None:
        if mirror_path.exists():
            for existing_path in sorted(mirror_path.rglob("*"), reverse=True):
                if existing_path.is_dir():
                    continue
                relative_path = existing_path.relative_to(mirror_path)
                if relative_path not in desired_files:
                    existing_path.unlink()
            for existing_dir in sorted(mirror_path.rglob("*"), reverse=True):
                if existing_dir.is_dir() and not any(existing_dir.iterdir()):
                    existing_dir.rmdir()

        for relative_path in desired_files:
            source_path = workspace_root / relative_path
            destination_path = mirror_path / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    def _build_metadata_payload(
        self,
        workspace_root: Path,
        session: WorkSession,
        decision: PublishDecision,
        desired_files: set[Path],
    ) -> dict[str, object]:
        return {
            "published_at": datetime.now(UTC).isoformat(),
            "workspace_name": workspace_root.name,
            "workspace_relative_to_watched_root": self._relative_to_root(
                workspace_root,
                self.config.data.watched_root,
            ),
            "publishable": decision.publishable,
            "activity_score": decision.score,
            "recent_file_count": session.recent_file_count,
            "recent_code_file_count": session.recent_code_file_count,
            "files_published": len(desired_files),
            "reasons": decision.reasons,
            "blockers": decision.blockers,
        }

    def _default_commit_message(self, workspace_root: Path) -> str:
        prefix = self.publisher.commit_message_prefix.strip() or "pulse"
        return f"{prefix}: sync {workspace_root.name} snapshot"

    def _matches_exclude(self, relative_path: Path) -> bool:
        relative_text = relative_path.as_posix()
        parts = relative_path.parts
        for pattern in self.publisher.exclude_globs:
            if fnmatch.fnmatch(relative_text, pattern):
                return True
            if pattern in parts:
                return True
        return False

    def _ensure_within_watched_root(self, workspace_root: Path, watched_root: Path) -> None:
        try:
            workspace_root.relative_to(watched_root)
        except ValueError as error:
            raise PrivatePublisherError(
                "workspace must live inside the configured watched_root"
            ) from error

    def _ensure_distinct_paths(self, workspace_root: Path, target_repo: Path) -> None:
        try:
            target_repo.relative_to(workspace_root)
            raise PrivatePublisherError(
                "target private repo cannot live inside the workspace being mirrored"
            )
        except ValueError:
            pass
        try:
            workspace_root.relative_to(target_repo)
            raise PrivatePublisherError(
                "workspace cannot live inside the target private repo"
            )
        except ValueError:
            pass

    def _ensure_git_repo(self, repo_root: Path) -> None:
        if not repo_root.exists():
            raise PrivatePublisherError(f"target repo path does not exist: {repo_root}")
        git_metadata = repo_root / ".git"
        if not git_metadata.exists():
            raise PrivatePublisherError(f"target path is not a git repo: {repo_root}")

    def _ensure_remote_exists(self, repo_root: Path) -> None:
        remote = self._git(repo_root, "remote").stdout.strip()
        if "origin" not in remote.splitlines():
            raise PrivatePublisherError(
                "target repo has no 'origin' remote; review locally or add a remote before pushing"
            )

    def _ensure_clean_target_repo(self, repo_root: Path) -> None:
        status = self._git(repo_root, "status", "--short").stdout.strip()
        if status:
            raise PrivatePublisherError(
                "target private repo is not clean; review or commit its changes before publishing"
            )

    def _current_branch(self, repo_root: Path) -> str:
        return self._git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def _switch_branch(self, repo_root: Path, branch: str) -> None:
        verify = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", branch],
            capture_output=True,
            text=True,
        )
        if verify.returncode == 0:
            self._git(repo_root, "switch", branch)
        else:
            self._git(repo_root, "switch", "-c", branch)

    def _changed_files(self, repo_root: Path) -> list[str]:
        status = self._git(repo_root, "status", "--short").stdout.splitlines()
        return [line.strip() for line in status if line.strip()]

    def _stage_managed_paths(
        self,
        repo_root: Path,
        mirror_subdirectory: Path,
        metadata_relative_path: Path,
    ) -> None:
        mirror_arg = "." if str(mirror_subdirectory) == "." else mirror_subdirectory.as_posix()
        self._git(
            repo_root,
            "add",
            "--all",
            "--",
            mirror_arg,
            metadata_relative_path.as_posix(),
        )

    def _should_push(self, explicit_push: bool) -> bool:
        if explicit_push:
            return True
        return self.publisher.push_after_commit and not self.publisher.require_explicit_push

    def _relative_to_root(self, path: Path, root: Path) -> str:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            return path.name

    def _git(self, repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", "-C", str(repo_root), *args],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise PrivatePublisherError(error.stderr.strip() or error.stdout.strip()) from error
