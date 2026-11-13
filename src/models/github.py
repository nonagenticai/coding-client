"""GitHub integration models for repository operations and webhook handling.

This module provides comprehensive data models for GitHub API integration, supporting
repository operations, pull request management, webhook processing, and code analysis
workflows. The models facilitate seamless integration between GitHub's API and the
code graph helper system.

The GitHub integration supports:
- Repository cloning and synchronization
- Pull request analysis and validation
- Webhook event processing
- Code snippet evaluation in repository context
- Automated PR creation and management
- User and organization data handling

Key Model Categories:
    Core GitHub Models: GitHubUser, GitHubRepository, GitHubCommit for basic entities
    Pull Request Models: PullRequestData, PullRequest for PR operations
    Webhook Models: GitHubWebhookPayload for event processing
    Workspace Models: RepoWorkspace, RepoSetupResult for repository management
    Request Models: SnippetAnalysisRequest, PRCreationRequest for API operations

Example:
    ```python
    from github_models import GitHubRepository, PullRequestData, RepoSetupResult

    # Repository information
    repo = GitHubRepository(
        id=123456,
        name="my-project",
        full_name="owner/my-project",
        description="A sample project",
        url="https://github.com/owner/my-project",
        clone_url="https://github.com/owner/my-project.git",
        default_branch="main",
        language="Python",
        size=1024,
        stargazers_count=42,
        forks_count=7,
        open_issues_count=3,
        private=False,
        owner=GitHubUser(...)
    )

    # Pull request data
    pr = PullRequestData(
        number=123,
        title="Add new feature",
        state="open",
        author="contributor",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        base_branch="main",
        head_branch="feature/new-feature",
        url="https://github.com/owner/my-project/pull/123"
    )
    ```
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PullRequestData(BaseModel):
    """Pull request data model."""

    number: int = Field(..., description="Pull request number")
    title: str = Field(..., description="Pull request title")
    message: str | None = Field(None, description="Pull request message")
    state: str = Field(..., description="Pull request state (open, closed, merged)")
    author: str = Field(..., description="Pull request author")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    merged_at: datetime | None = Field(None, description="Merge timestamp")
    base_branch: str = Field(..., description="Base branch")
    head_branch: str = Field(..., description="Head branch")
    url: str = Field(..., description="Pull request URL")
    diff_url: str = Field(..., description="Diff URL")
    patch_url: str = Field(..., description="Patch URL")


class GitHubUser(BaseModel):
    """GitHub user model."""

    login: str = Field(..., description="Username")
    id: int = Field(..., description="User ID")
    avatar_url: str = Field(..., description="Avatar URL")
    url: str = Field(..., description="User URL")
    type: str = Field(..., description="User type")


class GitHubRepository(BaseModel):
    """GitHub repository model."""

    id: int = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name")
    description: str | None = Field(None, description="Repository description")
    url: str = Field(..., description="Repository URL")
    clone_url: str = Field(..., description="Clone URL")
    ssh_url: str = Field(..., description="SSH URL")
    default_branch: str = Field(..., description="Default branch")
    language: str | None = Field(None, description="Primary language")
    size: int = Field(..., description="Repository size")
    stargazers_count: int = Field(..., description="Number of stars")
    forks_count: int = Field(..., description="Number of forks")
    open_issues_count: int = Field(..., description="Number of open issues")
    private: bool = Field(..., description="Whether repository is private")
    owner: GitHubUser = Field(..., description="Repository owner")


class GitHubCommit(BaseModel):
    """GitHub commit model."""

    sha: str = Field(..., description="Commit SHA")
    message: str = Field(..., description="Commit message")
    author: GitHubUser = Field(..., description="Commit author")
    committer: GitHubUser = Field(..., description="Commit committer")
    timestamp: datetime = Field(..., description="Commit timestamp")
    url: str = Field(..., description="Commit URL")


class GitHubIssue(BaseModel):
    """GitHub issue model."""

    number: int = Field(..., description="Issue number")
    title: str = Field(..., description="Issue title")
    message: str | None = Field(None, description="Issue message")
    state: str = Field(..., description="Issue state")
    author: GitHubUser = Field(..., description="Issue author")
    assignees: list[GitHubUser] = Field(default_factory=list, description="Issue assignees")
    labels: list[str] = Field(default_factory=list, description="Issue labels")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    closed_at: datetime | None = Field(None, description="Close timestamp")
    url: str = Field(..., description="Issue URL")


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload model."""

    action: str = Field(..., description="Webhook action")
    repository: GitHubRepository = Field(..., description="Repository data")
    sender: GitHubUser = Field(..., description="Event sender")
    pull_request: PullRequestData | None = Field(None, description="Pull request data")
    issue: GitHubIssue | None = Field(None, description="Issue data")
    commits: list[GitHubCommit] | None = Field(None, description="Commit data")
    ref: str | None = Field(None, description="Git reference")
    before: str | None = Field(None, description="Before SHA")
    after: str | None = Field(None, description="After SHA")


# Additional GitHub-specific models (consolidated from github_dataclasses.py)


class GitHubRepoInfo(BaseModel):
    """GitHub repository information."""

    owner: str = Field(..., description="Repository owner")
    name: str = Field(..., description="Repository name")
    url: str = Field(..., description="Repository URL")
    default_branch: str = Field("main", description="Default branch")
    description: str | None = Field(None, description="Repository description")
    language: str | None = Field(None, description="Primary language")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CloneResult(BaseModel):
    """Result of repository cloning operation."""

    success: bool = Field(..., description="Whether cloning was successful")
    repo_id: str = Field(..., description="Repository identifier")
    local_path: str = Field(..., description="Local path where repo was cloned")
    error: str | None = Field(None, description="Error message if cloning failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SyncResult(BaseModel):
    """Result of repository synchronization."""

    success: bool = Field(..., description="Whether sync was successful")
    commits_behind: int = Field(0, description="Number of commits behind")
    has_updates: bool = Field(False, description="Whether there are updates available")
    error: str | None = Field(None, description="Error message if sync failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CodeSnippet(BaseModel):
    """Code snippet model for GitHub operations."""

    code: str = Field(..., description="Code content")
    language: str = Field(..., description="Programming language")
    file_path: str | None = Field(None, description="File path")
    line_number: int | None = Field(None, description="Line number")
    description: str | None = Field(None, description="Code description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RepositoryContext(BaseModel):
    """Context information about a repository."""

    existing_patterns: list[dict[str, Any]] = Field(
        default_factory=list, description="Existing code patterns"
    )
    style_guide: dict[str, Any] = Field(default_factory=dict, description="Style guide rules")
    api_surface: dict[str, Any] = Field(default_factory=dict, description="API surface analysis")
    size_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Repository size metrics"
    )


class PRFileChange(BaseModel):
    """File change information for pull requests."""

    file_path: str = Field(..., description="Path to changed file")
    change_type: str = Field(..., description="Type of change (added, modified, deleted)")
    content: str | None = Field(None, description="New file content")
    old_content: str | None = Field(None, description="Previous file content")
    additions: int = Field(0, description="Number of lines added")
    deletions: int = Field(0, description="Number of lines deleted")
    patch: str | None = Field(None, description="Git patch content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PullRequest(BaseModel):
    """Pull request model for GitHub operations."""

    id: str = Field(..., description="Pull request ID")
    number: int = Field(..., description="Pull request number")
    title: str = Field(..., description="Pull request title")
    description: str = Field(..., description="Pull request description")
    url: str = Field(..., description="Pull request URL")
    status: str = Field(..., description="Pull request status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    merged_at: datetime | None = Field(None, description="Merge timestamp")
    author: str = Field(..., description="Pull request author")
    base_branch: str = Field(..., description="Base branch")
    head_branch: str = Field(..., description="Head branch")
    labels: list[str] = Field(default_factory=list, description="Labels")
    reviewers: list[str] = Field(default_factory=list, description="Reviewers")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RepoWorkspace(BaseModel):
    """Repository workspace model."""

    repo_id: str = Field(..., description="Repository ID")
    repo_url: str = Field(..., description="Repository URL")
    local_path: str = Field(..., description="Local workspace path")
    branch: str = Field("main", description="Current branch")
    last_sync: datetime = Field(..., description="Last sync timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RepoSetupResult(BaseModel):
    """Result of repository setup operation."""

    success: bool = Field(..., description="Whether setup was successful")
    workspace: RepoWorkspace | None = Field(None, description="Created workspace")
    error: str | None = Field(None, description="Error message if setup failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SnippetAnalysisRequest(BaseModel):
    """Request for code snippet analysis."""

    snippet: CodeSnippet = Field(..., description="Code snippet to analyze")
    workspace_id: str = Field(..., description="Workspace ID for context")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class SnippetEvaluationRequest(BaseModel):
    """Request for code snippet evaluation."""

    workspace_id: str = Field(..., description="Workspace ID")
    snippet: CodeSnippet = Field(..., description="Code snippet to evaluate")
    evaluation_options: dict[str, Any] = Field(
        default_factory=dict, description="Evaluation options"
    )


class PRCreationRequest(BaseModel):
    """Request for pull request creation."""

    workspace_id: str = Field(..., description="Workspace ID")
    changes: list[PRFileChange] = Field(..., description="File changes")
    pr_data: PullRequestData = Field(..., description="Pull request data")
    analysis_options: dict[str, Any] = Field(default_factory=dict, description="Analysis options")
