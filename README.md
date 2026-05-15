# Project Pulse

[![CI](https://github.com/surilevi/project-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/surilevi/project-pulse/actions/workflows/ci.yml)

`Project Pulse` is a local-first activity scanner for turning recent filesystem and Git activity into explainable work-session decisions.

It is designed for developers who work across local folders, experiments, and private repositories, and want a reviewable signal of what changed recently without uploading raw workspace data by default.

## Features

- discovers active project workspaces under a configured root
- scores recent file activity, code-like changes, and Git signals
- explains why a workspace does or does not pass the current policy
- stores local session summaries in an ignored state directory
- optionally mirrors a reviewed workspace snapshot into a separate private repository clone
- includes audit checks for common path, config, and secret-leak mistakes

## Quick Start

```powershell
pip install -e .
Copy-Item project-pulse.example.toml project-pulse.local.toml
project-pulse scan
```

Edit `project-pulse.local.toml` when you want to scan a different root directory or tune the scoring thresholds.

## Configuration

Project Pulse reads configuration in this order:

1. `project-pulse.local.toml`
2. `project-pulse.toml`
3. `project-pulse.example.toml`
4. built-in defaults

Machine-specific settings belong in `project-pulse.local.toml`, which is ignored by Git.

Important settings:

- `watched_root`: root directory to scan
- `lookback_window_hours`: activity window for the current scan
- `minimum_recent_files`: minimum recent file count
- `minimum_recent_code_files`: minimum code-like recent file count
- `minimum_activity_score`: weighted score threshold
- `require_git_signal`: require uncommitted changes or recent commits
- `expose_absolute_paths_in_reports`: keep `false` unless absolute paths are intentional
- `low_signal_directory_names`: generated-output folders to ignore

## Commands

Run a scan:

```powershell
project-pulse scan
project-pulse scan --json
project-pulse scan --root .\some-project-root
```

Record and list local sessions:

```powershell
project-pulse session-record --workspace .\your-project
project-pulse session-list
project-pulse session-list --workspace .\your-project
```

Run the repository safety audit:

```powershell
project-pulse safety-audit
```

## Codex Desktop Integration

The optional Codex watcher records a session when the Codex desktop app opens. It is Windows-only and manual-only; the repository does not install a startup task.

Example local config:

```toml
[codex_integration]
enabled = true
workspace = ""
process_names = ["Codex.exe", "codex.exe"]
poll_seconds = 20
state_path = ".project-pulse-state/codex-watcher-state.json"
```

Manual checks:

```powershell
project-pulse codex-record-open
project-pulse codex-watch --max-polls 2
```

## Private Mirror Publishing

The private publisher is disabled by default. When enabled, it mirrors one reviewed workspace into a separate local clone and commits only the managed mirror path plus metadata.

Recommended workflow:

1. Clone the target private repository outside the watched workspace tree.
2. Set `[publisher].enabled = true` and configure `target_repo_path`.
3. Keep `mirror_subdirectory` relative, for example `workspace`.
4. Run `project-pulse publish-private --workspace .\your-project`.
5. Add `--push` only when the mirrored commit should be pushed immediately.

The publisher rejects unsafe path layouts, requires a clean target repository, and filters configured local-only files such as `.env`, `.env.*`, and `project-pulse.local.toml`.

## Safety Model

Project Pulse is built around explicit local review:

- reports use relative paths by default
- session state lives under `.project-pulse-state/`
- local config and common generated artifacts are ignored
- networked publishing is opt-in
- `project-pulse safety-audit` checks for common local-path, email, env-file, and token mistakes
- the optional pre-commit hook blocks staged local config, obvious local machine paths, and common secret patterns

## Development

```powershell
pip install -e .[dev]
git config core.hooksPath .githooks
python -m ruff check src tests
python -m pytest
python -m project_pulse safety-audit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) for the security policy.

## Roadmap

- diff-aware session summaries
- richer explanations for why a session passed or failed policy
- sanitized export formats for reviewed activity snapshots
