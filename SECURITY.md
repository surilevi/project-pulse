# Security Notes

`Project Pulse` scans local filesystem activity, so privacy defaults matter.

## Safe defaults in this repo

- machine-specific settings live in `project-pulse.local.toml`, which is ignored by Git
- the committed config file is a generic example with no personal paths
- CLI reports render paths relative to the watched root by default
- common local artifacts such as caches, logs, and virtual environments are ignored by Git
- Codex integration is manual-only; the repo does not ship a startup launcher for it

## Before publishing

- review `git status` carefully before every commit
- keep `project-pulse.local.toml` out of version control
- avoid committing generated reports if they contain private project names
- use a public-safe Git author identity for this repository
- inspect future features that push or export data so they do not include raw local paths unless explicitly enabled

## Threat model

This project is designed to help you reason about local work, not to upload your filesystem state automatically. Any future publisher integration should default to explicit opt-in behavior and sanitized outputs.
