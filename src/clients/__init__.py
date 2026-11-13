"""HTTP service clients for inter-service communication."""

from .base import ServiceClient, ServiceError
from .coding_ai import CodingAIClient
from .coding_analysis import CodingAnalysisClient
from .coding_containers import CodingContainersClient
from .coding_github import CodingGitHubClient
from .coding_realtime import CodingRealtimeClient
from .coding_security import CodingSecurityClient
from .coding_testing import CodingTestingClient
from .coding_workspaces import CodingWorkspacesClient

__all__ = [
    "ServiceClient",
    "ServiceError",
    "CodingAIClient",
    "CodingAnalysisClient",
    "CodingContainersClient",
    "CodingGitHubClient",
    "CodingRealtimeClient",
    "CodingSecurityClient",
    "CodingTestingClient",
    "CodingWorkspacesClient",
]
