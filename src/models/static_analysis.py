"""Static analysis models for comprehensive code analysis and validation.

This module provides sophisticated Pydantic models for static code analysis operations
including call graph analysis, function signature analysis, and advanced validation
techniques. The models support AI-driven code analysis workflows with comprehensive
validation capabilities across multiple programming languages.

The static analysis system enables:
- Call graph generation with visual representations and metrics
- Function signature analysis with type inference and documentation extraction
- Advanced validation using symbolic execution, taint analysis, and formal verification
- Documentation generation with architectural diagrams and API references
- Multi-language support for Python, JavaScript, and TypeScript

Key Model Categories:
    Request Models: CallGraphRequest, SignatureAnalysisRequest, AdvancedValidationRequest
    Response Models: CallGraphResponse, SignatureAnalysisResponse, AdvancedValidationResponse
    Data Models: CallGraphNode, FunctionSignature, SecurityIssue for analysis results
    Validation Models: SymbolicExecutionResult, TaintAnalysisResult, FormalVerificationResult
    Documentation Models: DocumentationRequest, DocumentationResponse for doc generation

Analysis Types:
    - Call Graph: Function call relationships and execution paths
    - Signature Analysis: Function signatures with type inference
    - Symbolic Execution: Edge case discovery and assertion validation
    - Taint Analysis: Security vulnerability detection through data flow
    - Formal Verification: Mathematical proof of code properties
    - Documentation: Automated generation of technical documentation

Security Features:
    - Multi-level security validation (LOW, MEDIUM, HIGH, CRITICAL)
    - Taint analysis for vulnerability detection
    - Security issue reporting with severity levels
    - Formal verification for critical code paths

Example:
    ```python
    from static_analysis_models import (
        CallGraphRequest, SignatureAnalysisRequest,
        OutputFormat, StaticAnalysisSecurityLevel, Language
    )

    # Call graph analysis request
    call_graph_request = CallGraphRequest(
        container_name="my-analysis-container",
        analysis_scope=["src/", "lib/"],
        output_format=OutputFormat.SVG,
        include_external=True,
        max_depth=15
    )

    # Function signature analysis request
    signature_request = SignatureAnalysisRequest(
        container_name="my-analysis-container",
        language=Language.PYTHON,
        include_type_inference=True,
        extract_docstrings=True,
        analyze_usage_patterns=True
    )

    # Advanced validation request
    validation_request = AdvancedValidationRequest(
        code_changes=[
            CodeChange(
                file_path="src/main.py",
                original_code="def process(data): return data",
                modified_code="def process(data: List[Dict]) -> Dict: return transform(data)",
                change_type=ChangeType.MODIFICATION
            )
        ],
        validation_types=[ValidationType.SYMBOLIC_EXECUTION, ValidationType.TAINT_ANALYSIS],
        security_level=StaticAnalysisSecurityLevel.HIGH
    )
    ```
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OutputFormat(StrEnum):
    """Output format options for call graph analysis.

    Defines the available output formats for call graph visualization and data export.
    Each format serves different purposes for analysis and presentation.

    Attributes:
        DOT: Graphviz DOT format for programmatic graph manipulation
        SVG: Scalable Vector Graphics format for web display and documentation
        JSON: JavaScript Object Notation format for data exchange and API responses
    """

    DOT = "dot"
    SVG = "svg"
    JSON = "json"


class StaticAnalysisSecurityLevel(StrEnum):
    """Security level options for advanced validation.

    Defines the security validation levels that determine the strictness and depth
    of security analysis performed during code validation.

    Attributes:
        LOW: Basic security checks with minimal performance impact
        MEDIUM: Standard security analysis with balanced performance
        HIGH: Comprehensive security validation with thorough analysis
        CRITICAL: Maximum security scrutiny for security-critical code paths
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentationType(StrEnum):
    """Documentation type options for automated documentation generation.

    Defines the types of documentation that can be automatically generated
    from code analysis results.

    Attributes:
        ARCHITECTURE: High-level architectural documentation with component diagrams
        API_REFERENCE: Detailed API documentation with function signatures and usage
        CHANGE_SUMMARY: Summary of code changes with impact analysis
    """

    ARCHITECTURE = "architecture"
    API_REFERENCE = "api_reference"
    CHANGE_SUMMARY = "change_summary"
    USER_GUIDE = "user_guide"


class DocumentationFormat(StrEnum):
    """Documentation format options for output generation.

    Defines the available output formats for generated documentation,
    each optimized for different use cases and presentation requirements.

    Attributes:
        MARKDOWN: Markdown format for README files and GitHub documentation
        HTML: HTML format for web-based documentation and portals
        SPHINX: Sphinx format for Python documentation with advanced features
    """

    MARKDOWN = "markdown"
    HTML = "html"
    SPHINX = "sphinx"


class Language(StrEnum):
    """Supported programming languages for static analysis.

    Defines the programming languages supported by the static analysis system,
    each with specialized analysis capabilities and language-specific features.

    Attributes:
        PYTHON: Python language support with AST analysis and type inference
        JAVASCRIPT: JavaScript language support with ES6+ features
        TYPESCRIPT: TypeScript language support with type annotations
    """

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


class StaticAnalysisChangeType(StrEnum):
    """Type of code changes for validation analysis.

    Defines the types of code changes that can be analyzed during validation,
    each requiring different validation strategies and risk assessments.

    Attributes:
        ADDED: New code that has been added to the codebase
        DELETED: Code that has been removed from the codebase
        MODIFIED: Existing code that has been modified or updated
        RENAMED: Code that has been moved or renamed
    """

    ADDED = "ADDED"
    DELETED = "DELETED"
    MODIFIED = "MODIFIED"
    RENAMED = "RENAMED"


# Alias for backward compatibility
ChangeType = StaticAnalysisChangeType


class ValidationType(StrEnum):
    """Types of advanced validation techniques available.

    Defines the advanced validation techniques that can be applied to code
    for comprehensive analysis and security assessment.

    Attributes:
        SYMBOLIC_EXECUTION: Symbolic execution for edge case discovery and path analysis
        TAINT_ANALYSIS: Data flow analysis for security vulnerability detection
        FORMAL_VERIFICATION: Mathematical verification of code properties and contracts
    """

    SYMBOLIC_EXECUTION = "symbolic_execution"
    TAINT_ANALYSIS = "taint_analysis"
    FORMAL_VERIFICATION = "formal_verification"


# Call Graph Analysis Models


class CallGraphRequest(BaseModel):
    """Request model for call graph analysis."""

    container_name: str = Field(..., description="Name of provisioned container to analyze")
    analysis_scope: list[str] = Field(
        default=["src/"], description="Directories to include in analysis"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.JSON, description="Output format for call graph"
    )
    include_external: bool = Field(default=False, description="Include external library calls")
    max_depth: int = Field(default=10, description="Maximum call depth to analyze")

    @field_validator("container_name")
    @classmethod
    def validate_container_name(cls, v):
        """Validate that the container name is not empty."""
        if not v or not v.strip():
            raise ValueError("container_name cannot be empty")
        return v.strip()


class StaticAnalysisCallGraphNode(BaseModel):
    """Individual node in call graph."""

    function: str = Field(..., description="Function name")
    module: str = Field(..., description="Module path")
    complexity: int = Field(..., description="Function complexity score")
    line_number: int | None = Field(None, description="Line number in source")


class StaticAnalysisCallGraphEdge(BaseModel):
    """Edge representing function call relationship."""

    from_function: str = Field(..., alias="from", description="Calling function")
    to_function: str = Field(..., alias="to", description="Called function")
    call_type: str = Field(..., description="Type of call (direct, indirect, etc.)")


class CallGraphMetrics(BaseModel):
    """Metrics about the call graph."""

    total_functions: int = Field(..., description="Total number of functions")
    max_call_depth: int = Field(..., description="Maximum call depth found")
    cyclic_dependencies: list[str] = Field(
        default=[], description="List of cyclic dependencies found"
    )


class CallGraphResponse(BaseModel):
    """Response model for call graph analysis."""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    call_graph: dict[str, Any] = Field(..., description="Call graph data structure")
    visual_output: str | None = Field(None, description="Base64 encoded visual representation")
    critical_paths: list[str] = Field(default=[], description="Critical execution paths")
    orphaned_functions: list[str] = Field(default=[], description="Functions with no callers")
    metrics: CallGraphMetrics = Field(..., description="Call graph metrics")


# Signature Analysis Models


class SignatureAnalysisRequest(BaseModel):
    """Request model for function signature analysis."""

    container_name: str = Field(..., description="Name of provisioned container to analyze")
    language: Language = Field(..., description="Programming language")
    include_type_inference: bool = Field(default=True, description="Run type inference analysis")
    extract_docstrings: bool = Field(default=True, description="Extract function docstrings")
    analyze_usage_patterns: bool = Field(
        default=True, description="Analyze function usage patterns"
    )

    @field_validator("container_name")
    @classmethod
    def validate_container_name(cls, v):
        """Validate that the container name is not empty."""
        if not v or not v.strip():
            raise ValueError("container_name cannot be empty")
        return v.strip()


class FunctionParameter(BaseModel):
    """Function parameter details."""

    name: str = Field(..., description="Parameter name")
    type: str | None = Field(None, description="Parameter type annotation")
    required: bool = Field(..., description="Whether parameter is required")
    default: str | None = Field(None, description="Default value if any")
    description: str | None = Field(None, description="Parameter description")


class FunctionComplexityMetrics(BaseModel):
    """Function complexity metrics."""

    cyclomatic: int = Field(..., description="Cyclomatic complexity")
    cognitive: int = Field(..., description="Cognitive complexity")


class StaticAnalysisFunctionSignature(BaseModel):
    """Comprehensive function signature information."""

    name: str = Field(..., description="Function name")
    module: str = Field(..., description="Module path")
    signature: str = Field(..., description="Complete function signature")
    parameters: list[FunctionParameter] = Field(default=[], description="Function parameters")
    return_type: str | None = Field(None, description="Return type annotation")
    docstring: str | None = Field(None, description="Function docstring")
    usage_examples: list[str] = Field(default=[], description="Example usage patterns")
    called_by: list[str] = Field(default=[], description="Functions that call this function")
    calls: list[str] = Field(default=[], description="Functions called by this function")
    complexity_metrics: FunctionComplexityMetrics = Field(..., description="Complexity metrics")


class SignatureAnalysisResponse(BaseModel):
    """Response model for signature analysis."""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    functions: list[StaticAnalysisFunctionSignature] = Field(
        default=[], description="List of analyzed functions"
    )
    type_coverage: float = Field(..., description="Type annotation coverage (0-1)")
    external_dependencies: list[str] = Field(
        default=[], description="External dependencies referenced"
    )
    total_functions: int = Field(..., description="Total number of functions analyzed")
    typed_functions: int = Field(..., description="Number of functions with type annotations")


# Advanced Validation Models


class CodeChange(BaseModel):
    """Individual code change for validation."""

    file_path: str = Field(..., description="Path to the file")
    original_code: str | None = Field(None, description="Original code")
    modified_code: str = Field(..., description="Modified code")
    change_type: StaticAnalysisChangeType = Field(..., description="Type of change")


class AdvancedValidationRequest(BaseModel):
    """Request model for advanced code validation."""

    container_name: str = Field(..., description="Container name to scope file paths")
    code_changes: list[CodeChange] = Field(..., description="List of code changes to validate")
    validation_types: list[ValidationType] = Field(
        ..., description="Types of validation to perform"
    )
    security_level: StaticAnalysisSecurityLevel = Field(
        default=StaticAnalysisSecurityLevel.MEDIUM,
        description="Security validation level",
    )


class SymbolicExecutionResult(BaseModel):
    """Results from symbolic execution."""

    status: str = Field(..., description="Execution status")
    edge_cases_found: list[str] = Field(default=[], description="Edge cases discovered")
    assertion_violations: list[str] = Field(default=[], description="Assertion violations found")


class SecurityIssue(BaseModel):
    """Security issue found during taint analysis."""

    severity: str = Field(..., description="Issue severity")
    type: str = Field(..., description="Type of security issue")
    location: str = Field(..., description="Location in code")
    flow_path: list[str] = Field(..., description="Data flow path")
    recommendation: str = Field(..., description="Resolve recommendation")


class TaintAnalysisResult(BaseModel):
    """Results from taint analysis."""

    status: str = Field(..., description="Analysis status")
    security_issues: list[SecurityIssue] = Field(default=[], description="Security issues found")


class FormalVerificationResult(BaseModel):
    """Results from formal verification."""

    status: str = Field(..., description="Verification status")
    properties_verified: list[str] = Field(default=[], description="Properties that were verified")
    coverage: float = Field(..., description="Verification coverage")


class StaticAnalysisValidationResult(BaseModel):
    """Validation results for a single file."""

    file_path: str = Field(..., description="Path to validated file")
    symbolic_execution: SymbolicExecutionResult | None = Field(
        None, description="Symbolic execution results"
    )
    taint_analysis: TaintAnalysisResult | None = Field(None, description="Taint analysis results")
    formal_verification: FormalVerificationResult | None = Field(
        None, description="Formal verification results"
    )
    safety_score: float | None = Field(
        None, description="Individual safety score for this file (0-1)"
    )


class AdvancedValidationResponse(BaseModel):
    """Response model for advanced validation."""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    validation_results: list[StaticAnalysisValidationResult] = Field(
        ..., description="Validation results per file"
    )
    overall_safety_score: float = Field(..., description="Overall safety score (0-1)")
    blocking_issues: list[str] = Field(default=[], description="Issues that block deployment")
    recommendations: list[str] = Field(default=[], description="General recommendations")


# Documentation Generation Models


class DocumentationRequest(BaseModel):
    """Request model for documentation generation."""

    container_name: str = Field(..., description="Name of provisioned container to analyze")
    doc_types: list[DocumentationType] = Field(
        ..., description="Types of documentation to generate"
    )
    include_diagrams: bool = Field(default=True, description="Include architectural diagrams")
    format: DocumentationFormat = Field(
        default=DocumentationFormat.MARKDOWN, description="Output format"
    )

    @field_validator("container_name")
    @classmethod
    def validate_container_name(cls, v):
        """Validate that the container name is not empty."""
        if not v or not v.strip():
            raise ValueError("container_name cannot be empty")
        return v.strip()


class DocumentationSection(BaseModel):
    """Individual documentation section."""

    content: str = Field(..., description="Documentation content")
    diagrams: list[str] = Field(default=[], description="Associated diagram files")
    coverage: float | None = Field(None, description="Documentation coverage")


class DocumentationResponse(BaseModel):
    """Response model for documentation generation."""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    documentation: dict[str, DocumentationSection] = Field(
        ..., description="Generated documentation sections"
    )
    generated_files: list[str] = Field(default=[], description="List of generated files")
    quality_score: float = Field(..., description="Documentation quality score (0-1)")


# Database Models for Persistence


class CallGraphAnalysis(BaseModel):
    """Database model for call graph analysis results."""

    id: str = Field(..., description="Analysis ID")
    repository_url: str = Field(..., description="Repository URL")
    analysis_config: dict[str, Any] = Field(..., description="Analysis configuration")
    call_graph_data: dict[str, Any] = Field(..., description="Call graph data")
    visual_outputs: dict[str, Any] = Field(..., description="Visual outputs")
    created_at: str = Field(..., description="Creation timestamp")


class SignatureAnalysis(BaseModel):
    """Database model for signature analysis results."""

    id: str = Field(..., description="Analysis ID")
    repository_url: str = Field(..., description="Repository URL")
    language: str = Field(..., description="Programming language")
    functions_data: dict[str, Any] = Field(..., description="Functions data")
    type_coverage: float = Field(..., description="Type coverage")
    created_at: str = Field(..., description="Creation timestamp")


class ValidationAnalysis(BaseModel):
    """Database model for validation analysis results."""

    id: str = Field(..., description="Analysis ID")
    code_changes: dict[str, Any] = Field(..., description="Code changes")
    validation_results: dict[str, Any] = Field(..., description="Validation results")
    safety_score: float = Field(..., description="Safety score")
    created_at: str = Field(..., description="Creation timestamp")
