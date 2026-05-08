# Public Repo Guide

This guide is for publishing `Project Pulse` safely as your first public repository.

## Before you publish

1. Keep `project-pulse.local.toml` local only.
2. From the repository root, run `python -m project_pulse public-audit`.
3. Read `git status --short --ignored` and make sure you understand every tracked file.
4. Make sure your repo-local Git email is your GitHub-provided `noreply` email, not a personal email.
5. Decide whether you want a software license before the first public push.

## Set a safe commit identity

On GitHub:

1. Open [GitHub email settings](https://github.com/settings/emails).
2. Turn on `Keep my email addresses private`.
3. Copy the GitHub-provided `noreply` email shown there.

In this repository:

```powershell
cd path\to\project-pulse
git config user.name "Suranyi Levente"
git config user.email "PASTE_YOUR_GITHUB_NOREPLY_EMAIL_HERE"
project-pulse public-audit
```

## Create the repository on GitHub

Open [Create a new repository](https://github.com/new) and use:

- Owner: `surilevi`
- Repository name: `project-pulse`
- Visibility: `Public`

Important:

- Do not add a README on GitHub.
- Do not add a `.gitignore` on GitHub.
- Do not add a license on GitHub unless you want to decide the license right now.

The local repo already has files, so letting GitHub pre-populate it can create an unnecessary merge situation.

## First publish from your machine

After the GitHub repo exists and your local email is set:

```powershell
cd path\to\project-pulse
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/surilevi/project-pulse.git
git push -u origin main
```

## After the first push

Check these pages on GitHub:

1. Repository home page
2. `Commits` page
3. `Settings` -> `General`
4. `Settings` -> `Security`

Confirm:

- your commit author email is private
- no local filesystem paths appear in the README or visible files
- no local config file was uploaded
- no secrets or tokens were committed

## Good first security habits

- Keep `Keep my email addresses private` enabled.
- Prefer repo-local Git config for public repos.
- Run `project-pulse public-audit` before pushes.
- Read `git diff --cached` before every commit.
- If you accidentally commit sensitive data, rotate the secret first, then clean the Git history.

## If you accidentally leak something

1. Stop pushing.
2. Rotate the exposed credential if it is a secret or token.
3. Remove the file or text locally.
4. Rewrite the repository history with `git-filter-repo`.
5. Force-push only after you understand the consequences.
6. If the data reached GitHub, review the cleanup guidance in the official docs.
