# coding-client — Shared Library Extraction Plan

## Purpose
Shared Python package that all `coding-*` microservices depend on. Contains models, auth, DB helpers, HTTP client base, config, and utilities extracted from the monolith.

## Package Name
`coding-client` (consumed as a pinned git dependency)

---

## Files to Extract

### 1. Pydantic Models (`src/models/`)
Copy from `src/app/models/`:

| Source File | Target | Notes |
|---|---|---|
| `core_models.py` | `models/core.py` | Base models used everywhere |
| `common_responses_models.py` | `models/responses.py` | Shared API response models |
| `code_graph_models.py` | `models/code_graph.py` | Graph node/edge models |
| `analysis_models.py` | `models/analysis.py` | Analysis request/response |
| `architecture_models.py` | `models/architecture.py` | Architecture analysis models |
| `testing_models.py` | `models/testing.py` | Test execution models |
| `testing_config.py` | `models/testing_config.py` | Test configuration |
| `test_executor_models.py` | `models/test_executor.py` | Executor request/response |
| `container_models.py` | `models/container.py` | Container lifecycle models |
| `docker_container_models.py` | `models/docker_container.py` | Docker-specific models |
| `github_models.py` | `models/github.py` | GitHub integration models |
| `pr_validation_models.py` | `models/pr_validation.py` | PR validation models |
| `security_models.py` | `models/security.py` | Security scan models |
| `agent_models.py` | `models/agent.py` | Agent request/response |
| `ai_test_failure_models.py` | `models/ai_test_failure.py` | AI failure analysis |
| `bug_models.py` | `models/bug.py` | Bug detection models |
| `logging_models.py` | `models/logging.py` | Structured logging models |
| `package_manager_models.py` | `models/package_manager.py` | Package manager models |
| `pydantic_ai_models.py` | `models/pydantic_ai.py` | PydanticAI integration |
| `repo_scanner_models.py` | `models/repo_scanner.py` | Repo scanner models |
| `static_analysis_models.py` | `models/static_analysis.py` | Static analysis models |
| `system_models.py` | `models/system.py` | System/infra models |
| `validation_models.py` | `models/validation.py` | Validation models |

### 2. Auth Layer (`src/auth/`)
Copy from `src/auth/`:

| Source File | Target | Notes |
|---|---|---|
| `dependencies.py` | `auth/dependencies.py` | FastAPI auth dependencies |
| `middleware.py` | `auth/middleware.py` | AuthMiddleware (Istio headers) |
| `models.py` | `auth/models.py` | Auth-specific models |
| `rbac.py` | `auth/rbac.py` | Role-based access control |
| `rbac_coding.py` | `auth/rbac_coding.py` | Coding-specific RBAC rules |
| `tenant.py` | `auth/tenant.py` | Multi-tenant support |

### 3. Database Layer (`src/db/`)
Copy from `src/app/db/`:

| Source File | Target | Notes |
|---|---|---|
| `__init__.py` | `db/__init__.py` | DB module init |
| `code_graph_database.py` | `db/code_graph_database.py` | Core DB operations |
| `database_path_manager.py` | `db/database_path_manager.py` | Path management |
| `db_types.py` | `db/db_types.py` | Custom DB types |
| `exceptions.py` | `db/exceptions.py` | DB-specific exceptions |
| `migrations.py` | `db/migrations.py` | Migration helpers |
| `performance_optimizer.py` | `db/performance_optimizer.py` | Query optimization |
| `postgres_connection.py` | `db/postgres_connection.py` | PostgreSQL connection pool |
| `tenant_query_helper.py` | `db/tenant_query_helper.py` | Tenant-scoped queries |
| `transaction_manager.py` | `db/transaction_manager.py` | Transaction management |
| `transaction_mixin.py` | `db/transaction_mixin.py` | Transaction mixin class |
| `transaction_patterns.py` | `db/transaction_patterns.py` | Common transaction patterns |
| `models/architecture.py` | `db/models/architecture.py` | Architecture ORM models |
Also copy `src/db.py` and `src/models.py` (top-level DB init)

### 4. Config (`src/config/`)
Copy from `src/app/config/`:

| Source File | Target | Notes |
|---|---|---|
| `__init__.py` | `config/__init__.py` | Config module |
| `yaml_config_loader.py` | `config/yaml_config_loader.py` | YAML config loading |

### 5. Interfaces (`src/interfaces/`)
Copy from `src/app/interfaces/` (all files — these define service contracts)

### 6. Types (`src/types/`)
Copy from `src/app/types/` (all files — shared type definitions)

### 7. Exceptions (`src/exceptions/`)
Copy from `src/app/exceptions/` (all files — exception hierarchy)

### 8. Utilities (`src/utils/`)
Copy from `src/app/utils/` — select shared utilities only (not service-specific ones)

### 9. HTTP Client Base (`src/clients/`)
**NEW CODE** — Create a base HTTP client class for service-to-service communication:
- `clients/base.py` — Base async HTTP client with retry, timeout, auth header forwarding
- `clients/coding_analysis.py` — Client stub for coding-analysis service
- `clients/coding_testing.py` — Client stub for coding-testing service
- `clients/coding_ai.py` — Client stub for coding-ai service
- `clients/coding_containers.py` — Client stub for coding-containers service
- `clients/coding_github.py` — Client stub for coding-github service
- `clients/coding_security.py` — Client stub for coding-security service
- `clients/coding_realtime.py` — Client stub for coding-realtime service

---

## Publishing
- No package index: consumers pin a commit of this repository
- All coding-* services add `coding-client` to their dependencies with a `[tool.uv.sources]` git pin
- CI builds the wheel as a check only
