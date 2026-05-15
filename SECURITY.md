# Security Policy

`Project Pulse` reads local filesystem metadata and can write local session state. Security and privacy issues are treated as core product issues, not secondary maintenance tasks.

## Supported Version

Security fixes target the current `main` branch.

## Reporting

Please do not post secrets, tokens, raw local configuration, or full private filesystem paths in public issues. If a report needs sensitive detail, share the smallest sanitized reproduction first and coordinate privately with the maintainer before sending raw data.

Useful reports include:

- a minimal command sequence
- operating system and Python version
- sanitized config fields relevant to the issue
- whether the problem affects scanning, session state, audit checks, or publishing

## Safety Defaults

- `project-pulse.local.toml` is ignored by Git
- `.project-pulse-state/` is ignored by Git
- reports use relative paths by default
- Codex integration is manual-only
- private publishing is disabled by default
- pushing from the private publisher requires an explicit command or explicit config opt-in
- safety audit and pre-commit checks look for common local-path, env-file, token, and private-key mistakes

## Operational Guidance

- Review generated reports before sharing them.
- Keep local config and session state out of version control.
- Use a separate private repository clone as the publisher target.
- Verify the target repository remote before using `publish-private --push`.
- Treat new export or publishing features as security-sensitive by default.
