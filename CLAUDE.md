# CLAUDE.md

Guidance for AI assistants (Claude Code and similar) working in this repository.

## Project overview

**Dynamic-industry** — "Dynamic industry Development."

This repository is in an **early / skeleton stage**. As of this writing it contains
only project scaffolding — there is no application source code, dependency manifest,
tests, or build configuration yet. The tooling setup (see `.gitignore`) targets a
**Python** project.

> **Keep this file honest.** When real code, dependencies, or workflows land, update
> the relevant sections below and remove the "not yet present" notes. Do not document
> structure, commands, or conventions that do not actually exist in the repo — describe
> what is here, not what is imagined.

## Current repository contents

```
.
├── README.md      # One-line project description
├── .gitignore     # Standard Python .gitignore (GitHub's Python template)
└── CLAUDE.md      # This file
```

There are no source directories, package manifests (`pyproject.toml`,
`requirements.txt`, `setup.py`), CI config, or test suites at this time.

## Language & tooling

The `.gitignore` is the canonical Python template and anticipates a broad range of
tools. Nothing below is wired up yet — these are the conventions to reach for as the
project grows, chosen to match what `.gitignore` already accounts for:

- **Language:** Python 3.
- **Packaging / dependencies:** any of `pip` (`requirements.txt`), `uv` (`uv.lock`),
  `poetry`, `pdm`, or `pipenv` are anticipated by `.gitignore`. Pick one when adding
  dependencies and record the choice here.
- **Virtual environments:** `.venv/`, `venv/`, `env/`, `ENV/` are all ignored. Prefer
  `.venv/` at the repo root.
- **Testing:** `pytest` is anticipated (`.pytest_cache/`, coverage artifacts ignored).
- **Type checking:** `mypy`, `pyre`, and `pytype` caches are ignored.
- **Linting / formatting:** `ruff` cache (`.ruff_cache/`) is ignored — Ruff is the
  suggested linter/formatter.

### Common commands (once the project is set up)

These are **not yet runnable** — no manifest or code exists. Use them as the expected
shape and update with the real invocations once tooling is added:

```bash
# Environment
python -m venv .venv && source .venv/bin/activate

# Install (depends on the packaging tool chosen)
pip install -r requirements.txt      # or: uv sync / poetry install / pdm install

# Test
pytest

# Lint & format
ruff check .
ruff format .

# Type check
mypy .
```

Do not invent a run command until an entry point actually exists.

## Secrets & environment

- `.env`, `.envrc`, and `local_settings.py` are git-ignored — **never commit secrets.**
- `db.sqlite3` and `*.log` are ignored; local databases and logs stay out of version
  control.

## Git workflow & conventions

- **Default branch:** `main`.
- **Feature branch for AI-assisted work:** `claude/claude-md-docs-f978f1` (the branch
  this documentation work targets). Develop on the assigned feature branch, not `main`.
- **Do not push directly to `main`.** Open changes on a feature branch.
- **Commits:** use clear, descriptive, imperative-mood messages
  (e.g. "Add data ingestion module", not "added stuff").
- **Pull requests:** only open a PR when explicitly requested. If a repo PR template
  appears under `.github/`, follow its structure.
- **Pushing:** `git push -u origin <branch-name>`.

## Guidance for AI assistants

1. **Verify before asserting.** This repo changes shape quickly from its skeleton
   state — check the actual files (`ls`, `git status`, read manifests) before relying
   on anything in this document.
2. **Scope work to what's requested.** Don't scaffold frameworks, add dependencies, or
   create directory structures unless the task calls for it.
3. **Keep this file current.** When you add real structure (packages, tests, build,
   CI), update the corresponding section and drop the "not yet present" caveats.
4. **Match existing conventions.** Once code exists, mirror its style, layout, and
   idioms rather than importing outside conventions.
5. **Never commit secrets** or files that belong under `.gitignore`.
