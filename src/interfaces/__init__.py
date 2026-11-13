"""Abstract interfaces for dependency injection and circular import prevention.

These interfaces define contracts for service interactions without
importing concrete implementations.
"""

from .cache_interface import IAnalysisCache, ICacheManager
from .container_interface import ContainerInfo as IContainerInfo
from .docker_interface import IDockerService
from .graph_interface import IGraphService
from .security_interface import ISecurityService
from .webhook_interface import IWebhookEventHandler

__all__ = [
    "IAnalysisCache",
    "ICacheManager",
    "IContainerInfo",
    "IDockerService",
    "IGraphService",
    "ISecurityService",
    "IWebhookEventHandler",
]
