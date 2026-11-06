# Contributing to Reaper

Thank you for helping improve Reaper. Bug reports, documentation fixes, tests, and focused code changes are all welcome.

## Set up the project

Reaper requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```console
git clone https://github.com/nikhil25803/reaper.git
cd reaper
uv sync --locked
uv pip install graphifyy==0.9.95
```

Confirm the local tools:

```console
uv run reaper --version
uv run reaper --check graphify
```

## Make a change

1. Create a focused branch from the latest `main`.
2. Keep the change as small as possible while fully solving the problem.
3. Add or update tests for behavior changes.
4. Update user-facing documentation when commands or output change.
5. Do not commit generated `reaper-analysis/`, build, cache, model, or environment files.

## Run the quality checks

```console
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

When changing the Bash workflow, also run:

```console
shellcheck scripts/reaper-workflow.sh
bash -n scripts/reaper-workflow.sh
```

PowerShell workflow changes are exercised by the Windows `System Prompt` GitHub Actions job.

## Report an issue

Include the operating system, Python and Reaper versions, command used, expected behavior, actual output, and the smallest project or graph that reproduces the problem. Remove secrets and private source code before attaching reports or logs.

## Pull-request checklist

- [ ] The change has one clear purpose.
- [ ] Tests cover new or changed behavior.
- [ ] Pytest, Ruff, formatting, and build checks pass.
- [ ] Bash or PowerShell checks pass when their scripts changed.
- [ ] README or command help is updated when user-facing behavior changed.
- [ ] Generated files, models, credentials, and unrelated edits are excluded.
