# coding-client

[![CI](https://github.com/nonagenticai/coding-client/actions/workflows/ci.yml/badge.svg)](https://github.com/nonagenticai/coding-client/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/nonagenticai/coding-client)](https://github.com/nonagenticai/coding-client/releases)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Shared Python library for the coding-* microservices ecosystem — models, auth, database, service clients, and utilities.

| | |
|---|---|
| **Stack** | Python 3.14 · Pydantic 2.x · SQLAlchemy 2.x · psycopg 3.x · httpx · structlog |
| **Package** | `coding-client` (Apache-2.0) |
| **Used by** | coding-gateway, coding-analysis, coding-testing, coding-ai, coding-containers, coding-github, coding-security, coding-realtime |

## What It Provides

**Models** (`coding_client.models`) — 23 domain-specific Pydantic models covering code graphs, architecture, analysis, testing, containers, GitHub, security, AI agents, bug tracking, package management, PR validation, and more.

**Auth** (`coding_client.auth`) — Istio header-based authentication middleware, RBAC helpers (`require_role`, `require_access_coding`), multi-tenant isolation (`TenantMiddleware`, `require_tenant`, `get_tenant_id`), and FastAPI dependencies (`get_current_user`).

**Database** (`coding_client.db`) — PostgreSQL connection management via PgBouncer, SQLite code graph database, transaction management (`TransactionManager`, `TransactionContext`), tenant-aware queries (`TenantQueryBuilder`), migrations, and 9 custom exceptions.

**Clients** (`coding_client.clients`) — service-to-service HTTP clients with retry and timeout, including the canonical `CodingWorkspacesClient` and the compatibility-only `CodingContainersClient`. All extend a common `ServiceClient` base.

**Utilities** (`coding_client.utils`) — 16 modules: file operations, filesystem ops, path utils, archive utils, async timeout, encoding helper, HTTP client, retry helper, profiling, response builder, content processing, database utils, constants, enum helpers, security validation, AST debug.

**Interfaces** (`coding_client.interfaces`) — 6 abstract contracts for dependency injection: `IGraphService`, `IDockerService`, `ISecurityService`, `IAnalysisCache`, `ICacheManager`, `IWebhookEventHandler`.

**Types** (`coding_client.types`) — Shared type definitions, enums, constraint types, and workflow state machine definitions.

**API** (`coding_client.api`) — FastAPI middleware (`RequestLoggingMiddleware`, `HealthCheckFilter`), exception handlers, and OpenAPI configuration helpers.

## Installation

Consumed as a **git dependency**, pinned to a commit:

```toml
[project]
dependencies = ["coding-client"]

[tool.uv.sources]
coding-client = { git = "https://github.com/nonagenticai/coding-client", rev = "<commit sha>" }
```

```bash
uv lock     # records the pinned commit in uv.lock
uv sync
```

No package index is involved, so this resolves identically on a laptop, in CI, and inside a
Docker build.

## Quick Start

```bash
uv sync
uv run pytest tests/ -v --cov=src
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run ty check .
```

## Architecture

```
src/
├── __init__.py
├── api/
│   ├── exception_handlers.py       # FastAPI exception handlers
│   ├── openapi_config.py           # OpenAPI customization
│   └── request_logging.py          # Request logging middleware
├── auth/
│   ├── dependencies.py             # FastAPI auth dependencies (get_current_user)
│   ├── middleware.py                # Istio header auth middleware
│   ├── models.py                   # User model
│   ├── rbac.py                     # Role-based access control
│   ├── rbac_coding.py              # Coding-specific RBAC helpers
│   └── tenant.py                   # Multi-tenant isolation
├── clients/
│   ├── base.py                     # ServiceClient base with retry/timeout
│   ├── coding_ai.py                # coding-ai client
│   ├── coding_analysis.py          # coding-analysis client
│   ├── coding_containers.py        # coding-containers client
│   ├── coding_workspaces.py        # canonical repository-workspace client
│   ├── coding_github.py            # coding-github client
│   ├── coding_realtime.py          # coding-realtime client
│   ├── coding_security.py          # coding-security client
│   └── coding_testing.py           # coding-testing client
├── config/
│   └── yaml_config_loader.py       # YAML config loading
├── db/
│   ├── code_graph_database.py      # SQLite graph DB
│   ├── database_path_manager.py    # DB file path management
│   ├── db_types.py                 # Database type definitions
│   ├── exceptions.py               # 9 custom DB exceptions
│   ├── migrations.py               # Schema migration helpers
│   ├── models/
│   │   └── architecture.py         # ORM models
│   ├── performance_optimizer.py    # Query performance tuning
│   ├── postgres_connection.py      # PostgreSQL via PgBouncer
│   ├── tenant_query_helper.py      # Tenant-aware query builder
│   ├── transaction_manager.py      # Transaction management
│   ├── transaction_mixin.py        # Transaction mixin
│   └── transaction_patterns.py     # Transaction patterns
├── exceptions/
│   ├── api_exceptions.py           # API exception hierarchy
│   └── pydantic_ai_exceptions.py   # PydanticAI-specific exceptions
├── interfaces/                     # 6 abstract contracts
├── models/                         # 23 Pydantic model files
├── types/
│   ├── constraint_types.py         # Validation constraints
│   ├── core_types.py               # Enums and type hints
│   └── state_machine.py            # Workflow state definitions
└── utils/                          # 16 utility modules
```

## Tests

```bash
uv run pytest tests/ -v --cov=src --cov-report=term-missing    # 29 test files
uv run ruff check src/ tests/                                   # Lint
uv run ruff format --check src/ tests/                          # Format check
uv run ty check .                                               # Type check
```

Test structure mirrors source: `test_api/`, `test_auth/`, `test_clients/`, `test_config/`, `test_db/`, `test_exceptions/`, `test_models/`, `test_types/`, `test_utils/`.

The suite needs no database. ⛔ `coding_client.db_init` has **no default DSN** (it used to
fall back to `localhost:5432/code_graph_helper`, a host Postgres deleted 2026-10-21):
importing it without `DATABASE_URL` / `TEST_DATABASE_URL` raises `RuntimeError` naming the
variable. A consumer that wants a test DB starts an ephemeral `postgres:18` container on a
random port — never a host `:5432`.

### Bypassing auth in a consumer's tests

`SKIP_AUTH=true` was **removed in 1.16.0**. It made `require_tenant`,
`optional_tenant` and `get_current_user_with_tenant` return the hardcoded tenant
`"test-tenant"` before examining any credential — an ambient, global switch
compiled into the production wheel, where one environment variable disabled
authentication for a whole service.

Use `coding_client.testing` instead. Same job for a test suite; per-app,
explicit, and impossible to switch on from the environment:

```python
from coding_client.testing import override_tenant_auth

@pytest.fixture
def client(app):
    undo = override_tenant_auth(app)          # or: with tenant_auth_override(app):
    yield TestClient(app)
    undo()                                     # restores the previous overrides exactly
```

It neutralises **every** identity dependency this SDK exposes, from one list.
That matters: hand-rolled override lists drift, and one in this fleet already
had — a consumer's conftest overrode three dependencies and not `require_tenant`,
and only worked because it also set `SKIP_AUTH`.

Pass `extra={dep: replacement}` for a service's own forked dependency object or a
service-specific return shape.

## CI

`.github/workflows/ci.yml` calls the public `nonagenticai/ci-workflows` python-library pipeline:
`ruff + ty + unit tests → uv build → bandit + pip-audit`, on GitHub-hosted runners with no
repository secrets. The wheel is a build artifact only — nothing is published to a package index;
consumers pin the git commit.

## Dependencies

| Category | Packages |
|----------|----------|
| **Web/API** | fastapi, httpx, PyJWT[crypto] |
| **Data** | pydantic, pydantic-settings, sqlalchemy[asyncio] |
| **Database** | psycopg[binary,pool] (PostgreSQL v3.x), aiosqlite |
| **Async** | redis, tenacity, aiofiles |
| **Observability** | structlog, opentelemetry-api, opentelemetry-sdk |
| **Security** | cryptography |
| **Utilities** | uuid-v7, cachetools, pyyaml |

## Security

Report vulnerabilities privately through the repository's Security tab — see
[`SECURITY.md`](SECURITY.md). Do not open a public issue for a security problem.

## Contributing

Issues and pull requests are welcome. See
[`CONTRIBUTING.md`](https://github.com/nonagenticai/.github/blob/main/CONTRIBUTING.md) for the
organisation-wide rules; setup, test and lint commands are in this README. Commits carry DCO
sign-off.

## License

Apache-2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
