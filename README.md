# coding-client

[![CI](https://github.com/nonagenticai/coding-client/actions/workflows/ci.yml/badge.svg)](https://github.com/nonagenticai/coding-client/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/nonagenticai/coding-client)](https://github.com/nonagenticai/coding-client/releases)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Shared Python library for the coding-* microservices ecosystem — Pydantic models, authentication
and tenant helpers, PostgreSQL access, typed service-to-service clients, an LLM agent base, and
test-side auth overrides. It is imported by services; it runs no process of its own.

| | |
|---|---|
| **Runtime** | Python 3.14 (`>=3.14,<3.15`) |
| **Depends on** | PostgreSQL 18 through PgBouncer, only when a consumer uses `coding_client.db_init` or `coding_client.db`; an OpenAI-compatible endpoint, only when it uses `coding_client.llm` |
| **Runs on** | Inside a consumer's FastAPI/Starlette process, or any Python 3.14 process |
| **Package** | `coding-client` (Apache-2.0), consumed as a pinned git dependency |

## What It Provides

**Models** (`coding_client.models`) — 23 model modules covering code graphs, architecture,
analysis, testing, containers, GitHub, security, AI agents, bug tracking, package management,
PR validation, and more.

**Auth** (`coding_client.auth`) — `AuthMiddleware` for Istio/header-based authentication, RBAC
helpers (`require_role`, `require_access_coding`), multi-tenant resolution
(`TenantMiddleware`, `require_tenant`, `get_tenant_id`, `get_current_user_with_tenant`),
header-trust posture (`trust_tenant_header`), on-behalf-of vouching, outbound identity headers,
WebSocket identity resolution, and the FastAPI dependency `get_current_user`.

**Database** (`coding_client.db`) — PostgreSQL connection management designed for PgBouncer,
tenant-aware query building (`TenantQueryBuilder`), database type aliases, and 9 custom
exceptions. There is no SQLite database in this package: the only `sqlite3` reference is
`sqlite3.OperationalError` in the retry helper's legacy exception list.

**Clients** (`coding_client.clients`) — typed HTTP service clients with retry and timeout,
including the canonical `CodingWorkspacesClient` and the compatibility-only
`CodingContainersClient`. All extend `ServiceClient`.

**Utilities** (`coding_client.utils`) — 16 modules: file operations, filesystem ops, path
utils, archive utils, async timeout, encoding helper, HTTP client, retry helper, profiling,
response builder, content processing, database utils, constants, enum helpers, security
validation, and AST debug.

**Interfaces** (`coding_client.interfaces`) — 7 abstract contracts for dependency injection:
`IGraphService`, `IDockerService`, `ISecurityService`, `IAnalysisCache`, `ICacheManager`,
`IWebhookEventHandler`, and `IContainerManager`, plus the `ContainerInfo` protocol.

**LLM** (`coding_client.llm`) — `BaseLLMAgent` over pydantic-ai, `LLMSettings`, request-scoped
identity headers (`llm_request_context`), an agent routing registry, and typed response models.

**Testing** (`coding_client.testing`) — `override_tenant_auth` / `tenant_auth_override`, the
supported replacement for the removed `SKIP_AUTH` environment switch.

**Types** (`coding_client.types`) — shared type definitions, enums, constraint types, and
workflow state machine definitions.

**API** (`coding_client.api`) — FastAPI exception handlers, OpenAPI configuration, request
logging (`RequestLoggingMiddleware`, `HealthCheckFilter`), logging setup, process-time metrics,
and a validation middleware/exception.

**Top-level modules** — `coding_client.telemetry` (OpenTelemetry trace setup),
`coding_client.db_init` (opt-in SQLAlchemy async engine/session; no default DSN), and
`coding_client.models_init` (SQLAlchemy ORM models for the code-graph schema).

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
git clone https://github.com/nonagenticai/coding-client.git
cd coding-client
uv sync
uv run python -c "import coding_client; print(coding_client.__name__)"
```

## Usage

Use an auth dependency in a FastAPI route:

```python
from fastapi import Depends, FastAPI

from coding_client.auth import require_tenant

app = FastAPI()


@app.get("/items")
async def items(tenant_id: str = Depends(require_tenant)) -> dict[str, str]:
    return {"tenant": tenant_id}
```

Call another coding-* service:

```python
from coding_client.clients import CodingWorkspacesClient

client = CodingWorkspacesClient(base_url="http://coding-containers:8080")
workspaces = await client.list_workspaces(headers={"X-Tenant-Id": "..."})
```

Each client also reads its service URL from the environment when `base_url` is omitted; it
raises `RuntimeError` if neither is available.

## Configuration

Every setting is read by the module that needs it; importing the library requires no
configuration. The settings a consumer is most likely to set:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | none | Read by `coding_client.db_init`; importing it without this (or `TEST_DATABASE_URL`) raises `RuntimeError` naming the variable. PostgreSQL only. |
| `TEST_DATABASE_URL` | none | Test-only fallback for `coding_client.db_init`. |
| `TRUST_TENANT_HEADER` | `true` | Whether client-supplied `X-Tenant-Id` / `X-User-Id` / `X-User-Roles` headers are believed. The default preserves existing deployments; set `false` once the service has a verifiable alternative. |
| `TRUSTED_CIDRS` | empty | CIDRs whose credential-less requests may use the network bypass. Empty by default. |
| `DEFAULT_TENANT_ID` | none | Fallback tenant for credential-less callers. There is deliberately no literal default: unset means such callers are rejected. |
| `LICENSE_INTROSPECT_URL` | empty | Licence introspection endpoint. Unset skips introspection; a presented licence token is then rejected. |
| `CODING_ONBEHALF_SUBJECTS` | empty | Comma-separated subjects allowed to vouch for other subjects. |
| `DEV_API_KEY` | empty | Development/testing API key; only honoured when `ENVIRONMENT` is `development` or `testing`. |
| `ENVIRONMENT` | `production` | Enables the production-only required-settings and bypass checks. |
| `OTEL_SDK_DISABLED` | `false` | Set `true` to disable OpenTelemetry setup. |
| `OTLP_TRACES_ENDPOINT` | empty | OTLP/HTTP trace exporter endpoint; no exporter without it. |
| `LLM_API_BASE_URL` | empty | OpenAI-compatible endpoint for `coding_client.llm`. |
| `LLM_API_KEY` | empty | Credential for that endpoint; must be non-empty for the SDK. |
| `LLM_MODE` | `inference_router` | `inference_router` (provider chain) or `direct`. |
| `CODING_<SERVICE>_URL` | empty | Per-client base URL, e.g. `CODING_AI_URL`, `CODING_ANALYSIS_URL`, `CODING_CONTAINERS_URL` (also used by `CodingWorkspacesClient`), `CODING_GITHUB_URL`, `CODING_REALTIME_URL`, `CODING_SECURITY_URL`, `CODING_TESTING_URL`. |

## Architecture

```
src/
├── __init__.py
├── db_init.py                      # opt-in SQLAlchemy async engine/session (no default DSN)
├── models_init.py                  # SQLAlchemy ORM models for the code-graph schema
├── telemetry.py                    # OpenTelemetry trace setup
├── testing.py                      # override_tenant_auth / tenant_auth_override
├── api/
│   ├── exception_handlers.py       # FastAPI exception handlers
│   ├── logging_setup.py            # Logging configuration
│   ├── metrics.py                  # Process-time header
│   ├── openapi_config.py           # OpenAPI customization
│   ├── request_logging.py          # Request logging middleware
│   └── validation.py               # Validation middleware and exception
├── auth/
│   ├── _default_tenant.py          # Fallback tenant resolution (no literal default)
│   ├── _header_trust.py            # TRUST_TENANT_HEADER posture
│   ├── _onbehalf.py                # On-behalf-of vouching
│   ├── _trusted_networks.py        # TRUSTED_CIDRS network bypass
│   ├── dependencies.py             # FastAPI auth dependencies (get_current_user)
│   ├── middleware.py               # Auth middleware
│   ├── models.py                   # User model
│   ├── outbound.py                 # Outbound identity headers
│   ├── rbac.py                     # Role-based access control
│   ├── rbac_coding.py              # Coding-specific RBAC helpers
│   ├── tenant.py                   # Multi-tenant isolation and licence introspection
│   └── websocket.py                # WebSocket identity resolution
├── clients/
│   ├── base.py                     # ServiceClient base with retry/timeout
│   ├── coding_ai.py                # coding-ai client
│   ├── coding_analysis.py          # coding-analysis client
│   ├── coding_containers.py        # coding-containers client
│   ├── coding_github.py            # coding-github client
│   ├── coding_realtime.py          # coding-realtime client
│   ├── coding_security.py          # coding-security client
│   ├── coding_testing.py           # coding-testing client
│   └── coding_workspaces.py        # canonical repository-workspace client
├── config/
│   ├── base_settings.py            # Production required-settings enforcement
│   └── yaml_config_loader.py       # YAML config loading
├── db/
│   ├── db_types.py                 # Database type definitions
│   ├── exceptions.py               # 9 custom DB exceptions
│   ├── postgres_connection.py      # PostgreSQL connection management (PgBouncer)
│   └── tenant_query_helper.py      # Tenant-aware query builder
├── exceptions/
│   ├── api_exceptions.py           # API exception hierarchy
│   └── pydantic_ai_exceptions.py   # PydanticAI-specific exceptions
├── interfaces/                     # 7 abstract contracts + ContainerInfo protocol
├── llm/
│   ├── base_agent.py               # BaseLLMAgent over pydantic-ai
│   ├── context.py                  # Request-scoped identity headers
│   ├── responses.py                # Typed LLM response models
│   ├── routing.py                  # Agent routing registry
│   └── settings.py                 # LLMSettings
├── models/                         # 23 Pydantic model modules
├── types/
│   ├── constraint_types.py         # Validation constraints
│   ├── core_types.py               # Enums and type hints
│   └── state_machine.py            # Workflow state definitions
└── utils/                          # 16 utility modules
```

## Development

```bash
uv sync
uv run pytest tests/ -v --cov=src --cov-report=term-missing    # 44 test modules
uv run ruff check src/ tests/                                   # Lint
uv run ruff format --check src/ tests/                          # Format check
uv run ty check .                                               # Type check
uv build                                                        # Wheel + sdist
```

Test structure mirrors source: `tests/unit/test_api/`, `test_auth/`, `test_clients/`,
`test_config/`, `test_db/`, `test_exceptions/`, `test_interfaces/`, `test_llm/`, `test_models/`,
`test_types/`, `test_utils/`, plus top-level tests for `db_init`, `telemetry`, and the testing
helper.

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
| **Web/API** | fastapi, starlette, httpx, PyJWT[crypto] |
| **Data** | pydantic, pydantic-settings, sqlalchemy[asyncio] |
| **Database** | psycopg[binary,pool] (PostgreSQL v3) |
| **Async** | redis, tenacity, aiofiles |
| **LLM** | pydantic-ai-slim[openai], openai, httpx2 |
| **Observability** | structlog, opentelemetry-api, opentelemetry-sdk |
| **Security** | cryptography, pyasn1 |
| **Utilities** | cachetools, pyyaml |

## Security

Report vulnerabilities privately through the repository's Security tab. Do not open a public
issue for a security problem.

## Contributing

Issues and pull requests are welcome. See
[`CONTRIBUTING.md`](https://github.com/nonagenticai/.github/blob/main/CONTRIBUTING.md) for the
organisation-wide rules; setup, test and lint commands are in this README. Commits carry DCO
sign-off.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
