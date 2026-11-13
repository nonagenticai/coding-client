"""
Docker Service interface for breaking circular dependencies.

This module provides abstract interfaces for Docker container operations to prevent
circular dependencies and enable dependency injection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.container import ContainerInfo, GitHubRepoRequest


class IDockerService(ABC):
    """Abstract interface for Docker container operations."""

    @abstractmethod
    def is_docker_available(self) -> bool:
        """Check if Docker is available and accessible.

        Returns:
            True if Docker is available, False otherwise
        """
        ...

    @abstractmethod
    def retry_docker_connection(self) -> bool:
        """Attempt to reconnect to Docker if it wasn't available initially.

        Returns:
            True if reconnection succeeded, False otherwise
        """
        ...

    @abstractmethod
    async def create_container(
        self, request: GitHubRepoRequest, env_vars: dict[str, str] | None = None
    ) -> ContainerInfo:
        """Create and start a Docker container for GitHub repository.

        Args:
            request: GitHub repository provisioning request
            env_vars: Optional environment variables from secret store

        Returns:
            ContainerInfo with container details
        """
        ...

    @abstractmethod
    async def remove_container(self, container: ContainerInfo) -> bool:
        """Remove existing container and cleanup.

        Args:
            container: Container info to remove

        Returns:
            True if removal succeeded, False otherwise
        """
        ...

    @abstractmethod
    async def remove_container_by_name(self, container_name: str) -> bool:
        """Remove a container by its name and clean up resources.

        Args:
            container_name: Name of the container to remove

        Returns:
            True if removal succeeded, False otherwise
        """
        ...

    @abstractmethod
    async def remove_container_by_id(self, docker_id: str, force: bool = True) -> None:
        """Remove a container by ID.

        Args:
            docker_id: Docker container ID
            force: Force removal even if running
        """
        ...

    @abstractmethod
    async def start_container(self, docker_id: str) -> None:
        """Start a container by ID.

        Args:
            docker_id: Docker container ID
        """
        ...

    @abstractmethod
    async def stop_container(self, docker_id: str, timeout: int = 10) -> None:
        """Stop a container by ID.

        Args:
            docker_id: Docker container ID
            timeout: Timeout in seconds before force kill
        """
        ...

    @abstractmethod
    async def list_containers(self) -> list[ContainerInfo]:
        """List all managed containers with real-time status verification.

        Returns:
            List of ContainerInfo objects
        """
        ...

    @abstractmethod
    async def find_container_by_name(self, container_name: str) -> ContainerInfo | None:
        """Find container by container_name.

        Args:
            container_name: Name of the container to find

        Returns:
            ContainerInfo if found, None otherwise
        """
        ...

    @abstractmethod
    async def find_existing_container(self, repo_url: str) -> ContainerInfo | None:
        """Find existing container by repository URL.

        Args:
            repo_url: Repository URL to search for

        Returns:
            ContainerInfo if found, None otherwise
        """
        ...

    @abstractmethod
    async def initialize_code_graph(
        self,
        container: ContainerInfo,
        analysis_settings: dict[str, Any] | None = None,
    ) -> ContainerInfo:
        """Manually initialize the code graph by calling the container's initialization endpoint.

        Args:
            container: Container info to initialize graph for
            analysis_settings: Optional analysis configuration

        Returns:
            Updated ContainerInfo
        """
        ...

    @abstractmethod
    async def read_container_file(
        self,
        container_name: str,
        file_path: str,
        offset: int = 0,
        length: int | None = None,
    ) -> dict[str, Any]:
        """Read file from container using docker exec.

        Args:
            container_name: Name of the container
            file_path: Path to the file inside the container
            offset: Starting offset for reading
            length: Number of bytes to read

        Returns:
            Dictionary with file content and metadata
        """
        ...

    @abstractmethod
    async def list_container_directory(
        self, container_name: str, path: str = "", recursive: bool = False
    ) -> list[dict[str, Any]]:
        """List directory contents in container.

        Args:
            container_name: Name of the container
            path: Directory path to list
            recursive: Whether to list recursively

        Returns:
            List of directory entries
        """
        ...

    @abstractmethod
    async def exec_in_container(
        self,
        docker_id: str,
        command: list[str],
        timeout: int = 30,
        environment: dict[str, str] | None = None,
        user: str | None = None,
    ) -> dict[str, Any]:
        """Execute command in container and return structured result.

        Args:
            docker_id: Docker container ID or name
            command: Command to execute as list of strings
            timeout: Execution timeout in seconds
            environment: Optional environment variables
            user: Optional user to run command as

        Returns:
            Dictionary with exit_code, stdout, stderr, execution_time, timeout
        """
        ...

    @abstractmethod
    async def create_file_in_container(
        self, docker_id: str, file_path: str, content: str, mode: str = "w"
    ) -> bool:
        """Create file with content in container.

        Args:
            docker_id: Docker container ID or name
            file_path: Path to create file at
            content: Content to write
            mode: Write mode ('w' for write, 'a' for append)

        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def get_container_stats(self, docker_id: str) -> dict[str, Any]:
        """Get resource usage statistics for container.

        Args:
            docker_id: Docker container ID or name

        Returns:
            Dictionary with resource statistics
        """
        ...

    @abstractmethod
    def get_language_container_image(self, language: str) -> str:
        """Get appropriate container image for language.

        Args:
            language: Programming language name

        Returns:
            Docker image name for the language
        """
        ...

    @abstractmethod
    async def create_test_container(self, config: dict[str, Any]) -> str:
        """Create container specifically for test execution.

        Args:
            config: Container configuration

        Returns:
            Container ID
        """
        ...

    @abstractmethod
    async def install_tools_in_container(
        self, docker_id: str, tools: list[str], language: str = "python"
    ) -> bool:
        """Install testing/quality tools in container.

        Args:
            docker_id: Docker container ID or name
            tools: List of tool names to install
            language: Programming language for tool installation

        Returns:
            True if successful, False otherwise
        """
        ...
