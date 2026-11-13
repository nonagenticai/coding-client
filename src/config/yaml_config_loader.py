"""Module for loading YAML configuration files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml: Any = None
from pydantic import ValidationError

from ..models.architecture import RepoConfig

logger = logging.getLogger(__name__)


class YamlConfigLoader:
    """Load and validate .codegraph.yml configuration files with versioning support."""

    # Current schema version - update when making breaking changes
    CURRENT_VERSION = "2.0"

    def __init__(self):
        """Initialize the YAML config loader with version migration mappings."""
        self._version_migrations = {
            # Map from version to migration function
            "1.0": self._migrate_v1_to_v2,
        }

    def load_config(self, repo: Path) -> RepoConfig:
        """Load configuration from .codegraph.yml with version detection and migration.

        Args:
            repo: Repository root path containing .codegraph.yml

        Returns:
            Validated RepoConfig object, migrated to current schema if needed

        Raises:
            ValueError: If config is invalid or cannot be migrated
        """
        cfg_path = repo / ".codegraph.yml"

        if not cfg_path.is_file():
            logger.info("No .codegraph.yml found at %s, using defaults", repo)
            return RepoConfig()

        if not HAS_YAML:
            logger.warning("yaml module not available - using defaults")
            return RepoConfig()

        assert yaml is not None, "yaml module must be available (guarded by HAS_YAML check)"
        try:
            # Load raw data for version detection
            raw_data = yaml.safe_load(cfg_path.read_text()) or {}

            # Check version and migrate if necessary
            config_version = self._detect_version(raw_data)

            if config_version != self.CURRENT_VERSION:
                logger.info(
                    "Config schema version %s detected, migrating to %s",
                    config_version,
                    self.CURRENT_VERSION,
                )
                raw_data = self._migrate_config(raw_data, config_version)

            # Create and validate the config object
            config = RepoConfig(**raw_data)

            # Store version information
            config.schema_version = self.CURRENT_VERSION

            return config

        except ValidationError as e:
            raise ValueError(f"Invalid .codegraph.yml: {e}") from e
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in .codegraph.yml: {e}") from e
        except Exception as e:
            logger.exception("Error processing .codegraph.yml")
            raise ValueError(f"Error reading .codegraph.yml: {e}") from e

    def _detect_version(self, data: dict[str, Any]) -> str:
        """Detect the schema version from config data.

        Args:
            data: Raw configuration dictionary

        Returns:
            Detected version string, defaults to "1.0" for legacy configs
        """
        # Check if version is explicitly provided
        if "schema_version" in data:
            return str(data["schema_version"])

        # Legacy detection logic
        if "detect_by" in data and isinstance(data["detect_by"], list):
            # This is likely a v1.0 config
            return "1.0"

        # Default for completely unknown formats
        return "1.0"

    def _migrate_config(self, data: dict[str, Any], from_version: str) -> dict[str, Any]:
        """Migrate configuration from one version to another.

        Args:
            data: Raw configuration dictionary
            from_version: Source version string

        Returns:
            Migrated configuration dictionary

        Raises:
            ValueError: If migration path doesn't exist
        """
        current = from_version
        config_data = data.copy()

        # Find migration path to current version
        while current != self.CURRENT_VERSION:
            if current not in self._version_migrations:
                raise ValueError(
                    f"No migration path from version {current} to {self.CURRENT_VERSION}"
                )

            # Apply migration step
            migration_func = self._version_migrations[current]
            config_data = migration_func(config_data)

            # Update to next version in chain
            # The migration function should return the new version
            current = config_data.get("schema_version", current)

        return config_data

    def _migrate_v1_to_v2(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from schema v1.0 to v2.0.

        Args:
            data: v1.0 config data

        Returns:
            v2.0 config data
        """
        # Make a copy to avoid modifying the original
        result = data.copy()

        # Set the new version
        result["schema_version"] = "2.0"

        # Handle renamed fields
        if "detection_strategy" in result:
            result["detect_by"] = result.pop("detection_strategy")

        # Handle format changes for layer definitions
        if "layers" in result:
            layers = result["layers"]

            # In v1, layers could be a basic list of names
            # In v2, they must be a dict mapping names to glob patterns
            if isinstance(layers, list):
                result["layers"] = {layer: ["**/*"] for layer in layers}

        return result
