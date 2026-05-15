from __future__ import annotations

import subprocess
from pathlib import Path

from project_pulse.audit import run_public_audit
from project_pulse.config import ProjectPulseConfig


def test_public_audit_flags_tracked_configured_local_state_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Audit Tester"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    (repo_root / "codex-state.json").write_text("{}", encoding="utf-8")
    subprocess.run(
        ["git", "add", "codex-state.json"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    config = ProjectPulseConfig.from_text(
        f"""
watched_root = "{repo_root.as_posix()}"
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
[session_persistence]
enabled = true
store_path = "{(repo_root / '.project-pulse-state' / 'sessions.json').as_posix()}"
session_gap_minutes = 90
max_sessions_per_workspace = 25
[codex_integration]
enabled = true
workspace = ""
process_names = ["Codex.exe"]
poll_seconds = 20
state_path = "{(repo_root / 'codex-state.json').as_posix()}"
""".strip()
    )

    findings = run_public_audit(repo_root, config)

    assert any(
        finding.path == "codex-state.json"
        and "tracked local state file" in finding.message
        for finding in findings
    )


def test_public_audit_flags_private_key_text(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Audit Tester"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    private_key_begin = "-----BEGIN " + "PRIVATE KEY-----"
    private_key_end = "-----END " + "PRIVATE KEY-----"
    (repo_root / "notes.txt").write_text(
        f"{private_key_begin}\nnot-real\n{private_key_end}\n",
        encoding="utf-8",
    )
    config = ProjectPulseConfig.from_text(
        f"""
watched_root = "{repo_root.as_posix()}"
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
[session_persistence]
enabled = true
store_path = "{(repo_root / '.project-pulse-state' / 'sessions.json').as_posix()}"
session_gap_minutes = 90
max_sessions_per_workspace = 25
""".strip()
    )

    findings = run_public_audit(repo_root, config)

    assert any(
        finding.path == "notes.txt"
        and "secret or access token" in finding.message
        for finding in findings
    )
