# Public Repo Guide

This guide is for keeping `Project Pulse` safe and professional as a public repository.

## Before each public push

1. Keep `project-pulse.local.toml` local only.
2. Run `python -m project_pulse public-audit` from the repository root.
3. Read `git status --short --ignored` and make sure you understand every tracked file.
4. Read `git diff --cached` before every commit.
5. Make sure your repo-local Git email is your GitHub-provided `noreply` email, not a personal email.

## Set a safe commit identity

On GitHub:

1. Open [GitHub email settings](https://github.com/settings/emails).
2. Turn on `Keep my email addresses private`.
3. Copy the GitHub-provided `noreply` email shown there.

In this repository:

```powershell
cd path\to\project-pulse
git config user.name "Your Public Name"
git config user.email "PASTE_YOUR_GITHUB_NOREPLY_EMAIL_HERE"
project-pulse public-audit
```

## Ongoing safety checks

Check these regularly on GitHub:

1. Repository home page
2. `Commits` page
3. `Security` tab
4. `Settings` -> `General`

Confirm:

- your commit author email is private
- no local filesystem paths appear in the README or visible files
- no local config file was uploaded
- no secrets or tokens were committed

## Good public-repo habits

- Keep `Keep my email addresses private` enabled.
- Prefer repo-local Git config for public repos.
- Run `project-pulse public-audit` before pushes.
- Use pull requests for non-trivial changes when possible.
- Keep documentation aligned with the actual shipped workflow.
- If you accidentally commit sensitive data, rotate the secret first, then clean the Git history.

## If you accidentally leak something

1. Stop pushing.
2. Rotate the exposed credential if it is a secret or token.
3. Remove the file or text locally.
4. Rewrite the repository history with `git-filter-repo`.
5. Force-push only after you understand the consequences.
6. If the data reached GitHub, review the cleanup guidance in the official docs.
