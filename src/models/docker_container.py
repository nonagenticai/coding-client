"""Docker-specific container models for internal container management.

This module provides Pydantic models that represent Docker containers and their
metadata within the code graph helper system. These models facilitate the management
of containerized development environments for code analysis.

The models in this module are specifically designed for internal use by the DockerService
and handle the conversion between Docker-specific representations and the public API models.

Classes:
    DockerContainerDetails: Internal representation of a Docker container with all
        Docker-specific metadata including ports, environment variables, and status.

Example:
    ```python
    from docker_container_models import DockerContainerDetails, ContainerStatus

    # Create container details
    container = DockerContainerDetails(
        docker_id="abc123",
        container_name="my-analysis-container",
        image="code-graph-helper:latest",
        ports={"8700/tcp": 8700},
        workspace_path="/app/workspace",
        status=ContainerStatus.RUNNING
    )

    # Convert to public API model
    api_model = container.to_container_info(
        code_graph_id="graph-123",
        repo_url="https://github.com/owner/repo"
    )
    ```
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .container import ContainerInfo, ContainerStatus


class DockerContainerDetails(BaseModel):
    """Docker-specific container details for internal use by DockerService."""

    docker_id: str
    container_name: str
    image: str
    ports: dict[str, int]
    environment: dict[str, str] = Field(default_factory=dict)
    workspace_path: str
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: ContainerStatus

    def to_container_info(
        self,
        code_graph_id: str = "",
        codebase_path: str = "/app/data/repo",
        repo_url: str = "",
        branch: str = "main",
        description: str | None = None,
    ) -> ContainerInfo:
        """Convert Docker-specific details to public ContainerInfo model.

        Transforms the internal Docker container representation into a public API model
        that hides Docker-specific implementation details while providing essential
        container information to API consumers.

        Args:
            code_graph_id (str, optional): Unique identifier for the associated code graph.
                Defaults to empty string.
            codebase_path (str, optional): Path to the codebase within the container.
                Defaults to "/app/data/repo".
            repo_url (str, optional): URL of the repository being analyzed.
                Defaults to empty string.
            branch (str, optional): Git branch being analyzed.
                Defaults to "main".
            description (Optional[str], optional): Human-readable description of the container.
                Defaults to None.

        Returns:
            ContainerInfo: Public API model containing essential container information
                including the container name, API endpoint URL, and status.

        Note:
            The method extracts the first available port mapping from the Docker container
            to construct the API endpoint URL. If no ports are mapped, it defaults to 8700.
        """

        # Get the first port mapping (usually there's only one)
        port = next(iter(self.ports.values()), 8700)

        return ContainerInfo(
            container_name=self.container_name,
            api_endpoint=f"http://localhost:{port}",
            code_graph_id=code_graph_id,
            codebase_path=codebase_path,
            repo_url=repo_url,
            branch=branch,
            status=self.status,
            description=description,
        )
