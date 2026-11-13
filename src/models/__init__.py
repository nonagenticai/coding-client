"""Pydantic models for the coding-client shared library.

Re-exports submodules for convenient access. Import specific classes from
their submodules to avoid circular imports:

    from coding_client.models.core import CoreCodeEntity, EntityType
    from coding_client.models.testing import TestRequest, TestResult
    from coding_client.models.container import ContainerInfo, ContainerStatus
"""

# Submodule re-exports (safe - no circular import risk)
from . import (
    agent,
    ai_test_failure,
    analysis,
    architecture,
    bug,
    code_graph,
    container,
    core,
    docker_container,
    github,
    logging,
    package_manager,
    pr_validation,
    pydantic_ai,
    repo_scanner,
    responses,
    security,
    static_analysis,
    system,
    test_executor,
    testing,
    testing_config,
    validation,
)

__all__ = [
    "agent",
    "ai_test_failure",
    "analysis",
    "architecture",
    "bug",
    "code_graph",
    "container",
    "core",
    "docker_container",
    "github",
    "logging",
    "package_manager",
    "pr_validation",
    "pydantic_ai",
    "repo_scanner",
    "responses",
    "security",
    "static_analysis",
    "system",
    "test_executor",
    "testing",
    "testing_config",
    "validation",
]
