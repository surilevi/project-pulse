from __future__ import annotations

from .models import ProjectPulseConfigData, PublishDecision, WorkSession


class MeaningfulChangeDetector:
    def __init__(self, config: ProjectPulseConfigData) -> None:
        self.config = config

    def evaluate(self, session: WorkSession) -> PublishDecision:
        score = self._score(session)
        repos_with_uncommitted_changes = sum(
            1 for repo in session.repositories if repo.has_uncommitted_changes
        )
        repos_with_recent_commits = sum(1 for repo in session.repositories if repo.has_recent_commit)

        metrics: dict[str, int | str | bool | None] = {
            "watched_root": session.watched_root.name or str(session.watched_root),
            "recent_file_count": session.recent_file_count,
            "recent_code_file_count": session.recent_code_file_count,
            "workspaces_with_activity": session.workspaces_with_activity,
            "repositories_with_uncommitted_changes": repos_with_uncommitted_changes,
            "repositories_with_recent_commits": repos_with_recent_commits,
            "activity_score": score,
        }

        reasons: list[str] = []
        blockers: list[str] = []

        if session.recent_file_count >= self.config.minimum_recent_files:
            reasons.append(
                f"recent file activity passed the minimum threshold ({session.recent_file_count} >= "
                f"{self.config.minimum_recent_files})"
            )
        else:
            blockers.append(
                f"recent file activity is below threshold ({session.recent_file_count} < "
                f"{self.config.minimum_recent_files})"
            )

        if session.recent_code_file_count >= self.config.minimum_recent_code_files:
            reasons.append(
                "recent code-like changes indicate substantive implementation work"
            )
        else:
            blockers.append(
                f"recent code-like changes are below threshold ({session.recent_code_file_count} < "
                f"{self.config.minimum_recent_code_files})"
            )

        if session.workspaces_with_activity >= self.config.minimum_workspaces_with_activity:
            reasons.append(
                "at least one project workspace shows activity inside the current session window"
            )
        else:
            blockers.append(
                "no project workspace met the minimum activity requirement in the current session window"
            )

        if score >= self.config.minimum_activity_score:
            reasons.append(
                f"weighted activity score passed the policy bar ({score} >= "
                f"{self.config.minimum_activity_score})"
            )
        else:
            blockers.append(
                f"weighted activity score is below the policy bar ({score} < "
                f"{self.config.minimum_activity_score})"
            )

        has_git_signal = repos_with_uncommitted_changes > 0 or repos_with_recent_commits > 0
        if self.config.require_git_signal and not has_git_signal:
            blockers.append("git-backed evidence is required but no recent Git signal was found")
        elif has_git_signal:
            reasons.append("Git state confirms the filesystem activity with repo-level evidence")

        publishable = not blockers
        return PublishDecision(
            publishable=publishable,
            score=score,
            reasons=reasons,
            blockers=blockers,
            metrics=metrics,
        )

    def _score(self, session: WorkSession) -> int:
        weights = self.config.weights
        repositories_with_uncommitted_changes = sum(
            1 for repo in session.repositories if repo.has_uncommitted_changes
        )
        repositories_with_recent_commits = sum(1 for repo in session.repositories if repo.has_recent_commit)
        return (
            session.recent_file_count * weights.recent_file
            + session.recent_code_file_count * weights.recent_code_file
            + repositories_with_uncommitted_changes
            * weights.repository_with_uncommitted_changes
            + repositories_with_recent_commits * weights.repository_with_recent_commit
        )
