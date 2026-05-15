# Contributing

Thanks for helping improve `Project Pulse`.

## Ground rules

- Keep privacy and local-safety defaults intact.
- Do not commit `project-pulse.local.toml`, `.project-pulse-state/`, or other machine-local artifacts.
- Prefer small, reviewable pull requests over broad refactors.
- If a feature affects publishing, scanning, or persistence, explain the safety impact in the pull request.

## Local setup

```powershell
pip install -e .[dev]
python -m ruff check src tests
python -m pytest
python -m project_pulse public-audit
```

## Before opening a pull request

1. Make sure tests pass locally.
2. Run `project-pulse public-audit`.
3. Read `git diff --cached` before committing.
4. Update docs when behavior changes.
5. Call out privacy, security, or workflow tradeoffs in the PR description.

## Good contribution targets

- scanner accuracy improvements
- safer publisher behavior
- better session explanations
- clearer docs and onboarding
- stronger tests for edge cases

## Please avoid

- hidden background automation
- silent networked behavior
- features that expose raw local paths by default
- fake activity generation or misleading contribution inflation
