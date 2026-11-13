"""
SQLAlchemy ORM models for code graph database.

Models include:
- Node: Code entities (functions, classes, modules) with multi-language support
- Edge: Relationships between entities (calls, imports, inheritance)
- Codebase: Repository/project tracking
- SchemaVersion: Migration tracking
- NodeAudit: Change audit logging
- Architecture analysis tables (components, metrics, patterns, packages)
- Quality analysis tables (results, sessions)
"""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from db_init import Base


class Node(Base):
    """Code entity node in the graph."""

    __tablename__ = "nodes"

    id = Column(String(500), primary_key=True)
    type = Column(String(50), nullable=False, index=True)
    properties = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    content_hash = Column(String(64), nullable=True, index=True)
    file_size = Column(Integer, nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    tsv = Column(TSVECTOR, nullable=True)

    __table_args__ = (
        Index("ix_nodes_type_created", "type", "created_at"),
        Index("ix_nodes_tenant_type", "tenant_id", "type"),
        Index("ix_nodes_tsv", "tsv", postgresql_using="gin"),
        Index("ix_nodes_properties", "properties", postgresql_using="gin"),
    )


class Edge(Base):
    """Relationship edge between code entities."""

    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(500), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    target = Column(String(500), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    relationship = Column(String(50), nullable=False)
    properties = Column(JSONB, nullable=True, default=dict)
    weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tenant_id = Column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "target", "relationship", name="uq_edges_source_target_rel"),
        Index("ix_edges_source", "source"),
        Index("ix_edges_target", "target"),
        Index("ix_edges_relationship", "relationship"),
        Index("ix_edges_source_rel", "source", "relationship"),
        Index("ix_edges_target_rel", "target", "relationship"),
        Index("ix_edges_weight", "relationship", "weight"),
        Index("ix_edges_tenant", "tenant_id"),
        Index("ix_edges_tenant_source", "tenant_id", "source"),
    )


class Codebase(Base):
    """Repository/project being analyzed."""

    __tablename__ = "codebases"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SchemaVersion(Base):
    """Tracks schema migration versions."""

    __tablename__ = "schema_version"

    version = Column(Integer, primary_key=True)
    description = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())


class NodeAudit(Base):
    """Audit log for node operations."""

    __tablename__ = "nodes_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(500), nullable=True)
    operation = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    tenant_id = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_nodes_audit_node_id", "node_id"),
        Index("ix_nodes_audit_tenant", "tenant_id"),
    )


# Architecture Analysis Tables


class ArchitectureComponent(Base):
    """Architecture component for dependency analysis."""

    __tablename__ = "architecture_components"

    id = Column(String(100), primary_key=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(200), nullable=False)
    files = Column(JSONB, nullable=False, default=list)
    dependencies = Column(JSONB, nullable=False, default=list)
    layer = Column(String(50), nullable=True)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_arch_components_codebase", "codebase_id"),
        Index("ix_arch_components_layer", "layer"),
        Index("ix_arch_components_tenant", "tenant_id"),
    )


class ArchitectureMetric(Base):
    """Architecture quality metrics (instability, abstractness, distance)."""

    __tablename__ = "architecture_metrics"

    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), primary_key=True
    )
    instability = Column(Float, nullable=False)
    abstractness = Column(Float, nullable=False)
    distance = Column(Float, nullable=False)
    tenant_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DetectedPattern(Base):
    """Detected design patterns in codebase."""

    __tablename__ = "detected_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    location = Column(String(500), nullable=False)
    confidence = Column(Float, nullable=False)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_detected_patterns_codebase", "codebase_id"),
        Index("ix_detected_patterns_name", "name"),
        Index("ix_detected_patterns_tenant", "tenant_id"),
    )


class ExternalPackage(Base):
    """External package dependencies with vulnerability tracking."""

    __tablename__ = "external_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(200), nullable=False)
    current_version = Column(String(50), nullable=False)
    latest_version = Column(String(50), nullable=True)
    license = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=True)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("codebase_id", "name", name="uq_external_packages_codebase_name"),
        Index("ix_external_packages_codebase", "codebase_id"),
        Index("ix_external_packages_severity", "severity"),
    )


class LayerAssignment(Base):
    """Layer assignments for architecture analysis."""

    __tablename__ = "layer_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    layer_name = Column(String(50), nullable=False)
    component_ids = Column(JSONB, nullable=False, default=list)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("codebase_id", "layer_name", name="uq_layer_assignments_codebase_layer"),
        Index("ix_layer_assignments_codebase", "codebase_id"),
    )


class QualityResult(Base):
    """Quality analysis results."""

    __tablename__ = "quality_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    overall_score = Column(Float, nullable=False)
    issues_count = Column(Integer, nullable=False)
    issues_data = Column(JSONB, nullable=True)
    summary_data = Column(JSONB, nullable=True)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_quality_results_codebase", "codebase_id"),)


class AnalysisSession(Base):
    """Analysis session tracking."""

    __tablename__ = "analysis_sessions"

    id = Column(String(100), primary_key=True)
    codebase_id = Column(
        String(100), ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False
    )
    analysis_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSONB, nullable=True)
    tenant_id = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_analysis_sessions_codebase", "codebase_id"),
        Index("ix_analysis_sessions_type", "analysis_type"),
        Index("ix_analysis_sessions_status", "status"),
    )
