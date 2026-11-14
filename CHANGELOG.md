# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `.github/workflows/publish.yml` — uploads to PyPI with Trusted Publishing (OIDC) on a `v*` tag,
  with `workflow_dispatch` for the first upload. It cannot live in the reusable
  `python-library.yml`: PyPI does not accept a reusable workflow as a Trusted Publisher
  (pypi/warehouse#11096).

### Changed

- **LLM plane moved to pydantic-ai 2.68 / openai 3.51**, which ended the dependency deadlock
  that made the scheduled Dependabot update job fail on every consumer for days. The two
  releases move together: `pydantic-ai-slim[openai]` 2.x requires `openai>=3.31`.
- `src/llm/{base_agent,context}.py` now build the shared client on **httpx2**, because openai 3
  types `AsyncOpenAI(http_client=...)` as `httpx2.AsyncClient`. The rest of the library keeps
  httpx 0.28 — separate packages, separate signatures, no overlap. The previously deferred
  `openai<3` ceiling (2026-11-06) is gone.
- `pyproject.toml`: publish metadata — `readme` (the PyPI project page now renders the README)
  and `[project.urls]`.

### Fixed

- `coding_client.models_init` imported `db_init` as a top-level module, so it could only be
  imported when `src/` happened to be on `sys.path`. In the installed package (and therefore in
  the wheel) it raised `ModuleNotFoundError`. Now a relative import.

## [1.21.2] - 2026-11-13

First public release.
