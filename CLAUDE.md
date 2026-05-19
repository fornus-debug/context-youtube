# CLAUDE.md — context-youtube

This file provides guidance for AI assistants (Claude Code and similar) working in this repository.

## Project overview

**context-youtube** is a newly initialized project. As of the initial commit, the repository contains only this documentation file and a minimal `README.md`. The project name suggests it involves YouTube video context — likely transcript extraction, video analysis, summarization, or related tooling.

Update this section as the project matures.

## Repository structure

```
context-youtube/
├── README.md        # Project title only (to be expanded)
└── CLAUDE.md        # This file
```

As source files are added, document them here.

## Development workflow

### Branch model

- `main` — stable, always releasable
- `claude/<short-description>` — AI-driven feature branches (e.g., the branch this file was authored on)
- Feature branches should be short-lived; open a pull request and merge promptly

### Commit conventions

Use concise, imperative-mood commit messages:

```
Add transcript extraction module
Fix timestamp parsing for live streams
Refactor context window chunking logic
```

- One logical change per commit
- Do not mix formatting changes with functional changes

### Pull requests

- Always open a draft PR when pushing a feature branch
- PR title mirrors the primary commit message
- PR body should include: what changed, why, and a brief test plan

## Code conventions (to be established)

As the language and framework are not yet determined, conventions will be added here once the project stack is chosen. Common expectations regardless of stack:

- No dead code or commented-out blocks committed to `main`
- No secrets, credentials, or API keys in source files — use environment variables
- Tests live alongside the code they cover (or in a top-level `tests/` directory)
- Linting and formatting enforced via CI before merge

## Environment variables

Document required environment variables here as they are introduced. Example format:

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | Yes | Google Data API v3 key for YouTube |

## Running the project

Commands will be added here once a runtime/build system is chosen.

## AI assistant notes

- This repository is in its earliest stage; no application code exists yet
- When adding the first source files, also update the "Repository structure" section above
- Prefer editing existing files over creating new ones unless a new module is genuinely needed
- Do not add speculative abstractions — implement exactly what is required
- Default branch for all development: `main`; create short-lived feature branches for each task
- After pushing any branch, open a draft pull request targeting `main`
