# Project Pulse

`Project Pulse` is a local-first scanner that watches your real work under a chosen root directory and turns it into an explainable publishing recommendation.

The current version focuses on the part that matters most for a trustworthy system:

- discover recent file activity
- detect project workspaces and optional Git evidence
- score work sessions using named policy inputs instead of hidden constants
- explain why a session should or should not be published
- optionally mirror one workspace into a separate local clone of a private repo

## Why this exists

If you do most of your work on your laptop, GitHub can under-report how much you actually ship. This tool is meant to bridge that gap honestly by reflecting genuine activity rather than fabricating it.

## Quick start

```powershell
pip install -e .
Copy-Item project-pulse.example.toml project-pulse.local.toml
# Edit project-pulse.local.toml and set watched_root to your real projects folder.
project-pulse scan
python -m project_pulse public-audit
```

## Configuration

The repo ships with `project-pulse.example.toml` and expects your machine-specific settings in `project-pulse.local.toml`, which is ignored by Git. Important inputs:

- `watched_root`: the main directory to scan
- `lookback_window_hours`: how far back the scanner treats activity as part of the current work session
- `minimum_recent_files`: minimum file activity before a session becomes publish-worthy
- `minimum_recent_code_files`: minimum code-like file changes before code work counts as meaningful
- `minimum_workspaces_with_activity`: minimum number of active project roots in the session
- `minimum_activity_score`: overall threshold produced by weighted signals
- `expose_absolute_paths_in_reports`: keep this `false` for public-safe reports
- `low_signal_directory_names`: generated-output folders to ignore when scoring activity
- `[publisher]`: opt-in private mirror settings for syncing one workspace into a separate local clone
- `[session_persistence]`: local-only session store settings for grouping scans into real work sessions
- `[codex_integration]`: optional local watcher that records a session when the Codex desktop app opens
- `weights`: named contributions to the activity score

## First commands

```powershell
project-pulse scan
project-pulse scan --json
project-pulse scan --root .\some-project-root
```

## Session Persistence

Session persistence is local-only and enabled by default. It writes to an ignored JSON store so you can turn repeated scans into real work sessions.

```powershell
project-pulse session-record --workspace .\your-project
project-pulse session-list
project-pulse session-list --workspace .\your-project
```

Sessions continue while new observations stay within `session_gap_minutes`; otherwise a new session starts.

## Codex Desktop Integration

If you always open the Codex desktop app when you start coding, Project Pulse can piggyback on that habit.

This integration is currently Windows-only.

Set this in `project-pulse.local.toml`:

```toml
[codex_integration]
enabled = true
workspace = ""
process_names = ["Codex.exe", "codex.exe"]
poll_seconds = 20
state_path = ".project-pulse-state/codex-watcher-state.json"
```

- Leave `workspace = ""` to record against your full `watched_root`.
- Set `workspace = "relative/path/inside/watched_root"` if you want Codex opens to always count toward one default project.
- A Codex-open record is an app-open observation layered on top of the normal scanner. It uses whatever recent activity already exists inside the current lookback window; it does not prove a fresh edit happened after launch.

Manual checks:

```powershell
project-pulse codex-record-open
project-pulse codex-watch --max-polls 2
```

Project Pulse does not currently ship a Windows startup installer for this feature. Hidden-startup PowerShell launchers are commonly flagged by endpoint protection products, so the Codex integration is intentionally manual for now.

## Private Publisher

The private publisher is disabled by default. It is meant for a review-first workflow:

1. Clone a private GitHub repo somewhere outside your watched workspace tree.
2. Set `[publisher].enabled = true` and point `target_repo_path` at that local clone.
3. Pick a safe `mirror_subdirectory` such as `workspace`.
4. Run:

```powershell
project-pulse publish-private --workspace .\your-project
```

That creates a commit in the private repo clone only if the workspace has meaningful changes after filtering. Add `--push` only when you want to publish immediately.

## Public repo safety

- keep `project-pulse.local.toml` local only
- reports use relative paths by default to avoid leaking your full filesystem layout
- review [SECURITY.md](SECURITY.md) before publishing or adding export features
- this repo can use a pre-commit hook that blocks commits with placeholder identity or staged local config
- use [PUBLIC_REPO_GUIDE.md](PUBLIC_REPO_GUIDE.md) for the first public push workflow

## Project hygiene

- review [CONTRIBUTING.md](CONTRIBUTING.md) before opening pull requests
- issue templates guide bug reports and feature requests
- Dependabot keeps Python and GitHub Actions dependencies current
- CODEOWNERS routes repository review responsibility

## Roadmap

- add diff summarization
- add sanitized public portfolio snapshots
