# Project Pulse

`Project Pulse` is a local-first scanner that watches your real work under a chosen root directory and turns it into an explainable publishing recommendation.

The first version does not push anything to GitHub yet. It focuses on the part that matters most for a trustworthy system:

- discover recent file activity
- detect project workspaces and optional Git evidence
- score work sessions using named policy inputs instead of hidden constants
- explain why a session should or should not be published

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
- `weights`: named contributions to the activity score

## First commands

```powershell
project-pulse scan
project-pulse scan --json
project-pulse scan --root .\some-project-root
```

## Public repo safety

- keep `project-pulse.local.toml` local only
- reports use relative paths by default to avoid leaking your full filesystem layout
- review [SECURITY.md](SECURITY.md) before publishing or adding export features
- this repo can use a pre-commit hook that blocks commits with placeholder identity or staged local config
- use [PUBLIC_REPO_GUIDE.md](PUBLIC_REPO_GUIDE.md) for the first public push workflow

## Roadmap

- add session persistence
- add diff summarization
- add private-repo publishing
- add sanitized public portfolio snapshots
