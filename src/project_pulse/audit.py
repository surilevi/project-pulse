from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ProjectPulseConfig

ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"/opt/"),
    re.compile(r"/srv/"),
    re.compile(r"/mnt/"),
    re.compile(r"/etc/"),
    re.compile(r"/var/"),
    re.compile(r"/tmp/"),
    re.compile(r"\\Users\\"),
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SUSPICIOUS_SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

SAFE_EMAIL_SUFFIXES = (
    "@users.noreply.github.com",
    "@example.com",
)

ABSOLUTE_PATH_SCAN_EXCLUSIONS = {
    ".githooks/pre-commit",
    "src/project_pulse/audit.py",
}
LOCAL_ONLY_DIRECTORY_NAMES = {
    ".project-pulse-state",
}


@dataclass(slots=True)
class AuditFinding:
    severity: str
    path: str
    message: str


def run_public_audit(repo_root: Path, config: ProjectPulseConfig) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    findings.extend(_check_git_identity(repo_root))
    findings.extend(_check_ignored_local_config(repo_root))
    findings.extend(_check_sensitive_tracked_files(repo_root, config))
    findings.extend(_scan_working_tree(repo_root, config))
    return findings


def render_audit_report(findings: list[AuditFinding]) -> str:
    if not findings:
        return "Public audit passed: no obvious repo-safety issues found."

    lines = ["Public audit findings"]
    for finding in findings:
        lines.append(f"- [{finding.severity}] {finding.path}: {finding.message}")
    return "\n".join(lines)


def _check_git_identity(repo_root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    name = _git_config_get(repo_root, "user.name")
    email = _git_config_get(repo_root, "user.email")

    if not name or name == "CHANGE BEFORE PUBLIC COMMIT":
        findings.append(
            AuditFinding(
                severity="high",
                path=".git/config",
                message="repo-local git user.name is still a placeholder",
            )
        )

    if not email:
        findings.append(
            AuditFinding(
                severity="high",
                path=".git/config",
                message="repo-local git user.email is not set",
            )
        )
    elif email == "change-this-before-public-commit@example.com":
        findings.append(
            AuditFinding(
                severity="high",
                path=".git/config",
                message="repo-local git user.email is still a placeholder",
            )
        )
    elif not email.endswith(SAFE_EMAIL_SUFFIXES):
        findings.append(
            AuditFinding(
                severity="medium",
                path=".git/config",
                message="repo-local git user.email is not a GitHub noreply or example address",
            )
        )
    return findings


def _check_ignored_local_config(repo_root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    local_config = repo_root / "project-pulse.local.toml"
    if local_config.exists():
        tracked = _git_ls_files(repo_root, local_config)
        if tracked:
            findings.append(
                AuditFinding(
                    severity="high",
                    path="project-pulse.local.toml",
                    message="machine-local config is tracked by git",
                )
            )
    return findings


def _check_sensitive_tracked_files(
    repo_root: Path,
    config: ProjectPulseConfig,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    tracked_files = _git_ls_files_all(repo_root)
    local_state_paths = _configured_local_state_paths(repo_root, config)
    for tracked_path in tracked_files:
        normalized = tracked_path.replace("\\", "/")
        if normalized.startswith(".project-pulse-state/"):
            findings.append(
                AuditFinding(
                    severity="high",
                    path=tracked_path,
                    message=(
                        "tracked session persistence artifacts should not be committed "
                        "to a public repository"
                    ),
                )
            )
        if normalized in local_state_paths:
            findings.append(
                AuditFinding(
                    severity="high",
                    path=tracked_path,
                    message=(
                        "tracked local state file should not be committed "
                        "to a public repository"
                    ),
                )
            )
        if re.search(r"(^|/)\.env(\..+)?$", normalized):
            findings.append(
                AuditFinding(
                    severity="high",
                    path=tracked_path,
                    message="tracked env file should not be committed to a public repository",
                )
            )
    return findings


def _configured_local_state_paths(
    repo_root: Path,
    config: ProjectPulseConfig,
) -> set[str]:
    configured_paths = {
        config.data.session_persistence.store_path.resolve(),
        config.data.codex_integration.state_path.resolve(),
    }
    relative_paths: set[str] = set()
    for configured_path in configured_paths:
        try:
            relative_paths.add(configured_path.relative_to(repo_root.resolve()).as_posix())
        except ValueError:
            continue
    return relative_paths


def _scan_working_tree(repo_root: Path, config: ProjectPulseConfig) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    ignored_dirs = set(config.data.ignored_directory_names)
    ignored_dirs.update(LOCAL_ONLY_DIRECTORY_NAMES)
    ignored_files = set(config.data.ignored_file_names)
    ignored_files.add("project-pulse.local.toml")

    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in ignored_dirs for part in file_path.parts):
            continue
        if file_path.name in ignored_files:
            continue
        relative_path = file_path.relative_to(repo_root)
        if relative_path.parts and relative_path.parts[0] == ".git":
            continue
        if _looks_binary(file_path):
            continue
        findings.extend(_scan_text_file(relative_path, file_path))
    return findings


def _scan_text_file(relative_path: Path, file_path: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    if file_path.name.endswith(".local.toml"):
        findings.append(
            AuditFinding(
                severity="high",
                path=str(relative_path),
                message="local-only config file exists in the repository tree",
            )
        )

    normalized_relative_path = relative_path.as_posix()
    if normalized_relative_path not in ABSOLUTE_PATH_SCAN_EXCLUSIONS:
        for pattern in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(content):
                findings.append(
                    AuditFinding(
                        severity="medium",
                        path=str(relative_path),
                        message="contains an absolute filesystem path",
                    )
                )
                break

    for secret_pattern in SUSPICIOUS_SECRET_PATTERNS:
        if secret_pattern.search(content):
            findings.append(
                AuditFinding(
                    severity="high",
                    path=str(relative_path),
                    message="contains text that looks like a secret or access token",
                )
            )
            break

    for match in EMAIL_PATTERN.finditer(content):
        email = match.group(0)
        if email.endswith(SAFE_EMAIL_SUFFIXES):
            continue
        findings.append(
            AuditFinding(
                severity="medium",
                path=str(relative_path),
                message=f"contains an email address: {email}",
            )
        )
        break

    return findings


def _git_config_get(repo_root: Path, key: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", "--local", "--get", key],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _git_ls_files(repo_root: Path, path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path.relative_to(repo_root))],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return bool(result.stdout.strip())


def _git_ls_files_all(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _looks_binary(file_path: Path) -> bool:
    try:
        with file_path.open("rb") as file_handle:
            chunk = file_handle.read(4096)
    except OSError:
        return True
    return b"\x00" in chunk
