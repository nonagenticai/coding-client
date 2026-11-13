"""Tests for coding_client.config.yaml_config_loader.YamlConfigLoader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from coding_client.config.yaml_config_loader import YamlConfigLoader
from coding_client.models.architecture import RepoConfig


class TestLoadConfigDefaults:
    """Loading config when no file exists or yaml is unavailable."""

    def test_no_config_file_returns_defaults(self, tmp_path: Path):
        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)
        assert isinstance(config, RepoConfig)
        assert config.schema_version == "2.0"

    def test_default_detect_by(self, tmp_path: Path):
        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)
        assert config.detect_by == ["folder", "build_file", "annotation"]

    def test_default_extract_docstrings(self, tmp_path: Path):
        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)
        assert config.extract_docstrings is True

    def test_default_min_pattern_confidence(self, tmp_path: Path):
        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)
        assert config.min_pattern_confidence == 0.7


class TestLoadConfigV2:
    """Loading a v2 YAML config file."""

    def test_v2_config_loaded_correctly(self, tmp_path: Path):
        cfg = {
            "schema_version": "2.0",
            "extract_docstrings": False,
            "min_pattern_confidence": 0.9,
            "detect_by": ["folder"],
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        assert config.schema_version == "2.0"
        assert config.extract_docstrings is False
        assert config.min_pattern_confidence == 0.9
        assert config.detect_by == ["folder"]

    def test_v2_with_layers(self, tmp_path: Path):
        cfg = {
            "schema_version": "2.0",
            "layers": {
                "domain": ["src/domain/**"],
                "infrastructure": ["src/infra/**"],
            },
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        assert config.layers == {
            "domain": ["src/domain/**"],
            "infrastructure": ["src/infra/**"],
        }

    def test_v2_empty_yaml_returns_defaults(self, tmp_path: Path):
        """An empty YAML file (safe_load returns {}) should use defaults."""
        (tmp_path / ".codegraph.yml").write_text("")

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        # Empty dict → detected as v1 → migrated → still produces valid defaults
        assert isinstance(config, RepoConfig)
        assert config.schema_version == "2.0"


class TestLoadConfigV1Migration:
    """v1 format configs are migrated to v2."""

    def test_v1_detection_strategy_renamed(self, tmp_path: Path):
        cfg = {
            "detection_strategy": ["folder", "build_file"],
            "extract_docstrings": True,
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        assert config.schema_version == "2.0"
        assert config.detect_by == ["folder", "build_file"]

    def test_v1_layers_list_converted_to_dict(self, tmp_path: Path):
        cfg = {
            "layers": ["domain", "application", "infrastructure"],
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        assert config.schema_version == "2.0"
        assert isinstance(config.layers, dict)
        assert set(config.layers.keys()) == {"domain", "application", "infrastructure"}
        for patterns in config.layers.values():
            assert patterns == ["**/*"]

    def test_v1_with_detect_by_list_triggers_v1_detection(self, tmp_path: Path):
        """Config with detect_by as a list and no schema_version → detected as v1."""
        cfg = {"detect_by": ["folder"]}
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        config = loader.load_config(tmp_path)

        assert config.schema_version == "2.0"


class TestVersionDetection:
    """Unit tests for _detect_version."""

    def test_explicit_version_returned(self):
        loader = YamlConfigLoader()
        assert loader._detect_version({"schema_version": "2.0"}) == "2.0"
        assert loader._detect_version({"schema_version": "3.5"}) == "3.5"

    def test_numeric_version_converted_to_string(self):
        loader = YamlConfigLoader()
        assert loader._detect_version({"schema_version": 2.0}) == "2.0"

    def test_legacy_detect_by_list_returns_v1(self):
        loader = YamlConfigLoader()
        assert loader._detect_version({"detect_by": ["folder"]}) == "1.0"

    def test_unknown_format_defaults_to_v1(self):
        loader = YamlConfigLoader()
        assert loader._detect_version({}) == "1.0"
        assert loader._detect_version({"some_field": "value"}) == "1.0"

    def test_detect_by_non_list_defaults_to_v1(self):
        loader = YamlConfigLoader()
        # detect_by exists but is not a list → not v1-style, falls to default
        assert loader._detect_version({"detect_by": "folder"}) == "1.0"


class TestMigrationErrors:
    """Migration edge cases and error paths."""

    def test_unknown_version_raises_value_error(self):
        loader = YamlConfigLoader()
        with pytest.raises(ValueError, match="No migration path"):
            loader._migrate_config({"schema_version": "99.0"}, "99.0")

    def test_invalid_yaml_raises_value_error(self, tmp_path: Path):
        (tmp_path / ".codegraph.yml").write_text("{{invalid: yaml: [")

        loader = YamlConfigLoader()
        with pytest.raises(ValueError, match="Invalid YAML"):
            loader.load_config(tmp_path)

    def test_invalid_config_values_raises_value_error(self, tmp_path: Path):
        """Fields that violate the Pydantic model raise ValueError."""
        cfg = {
            "schema_version": "2.0",
            "min_pattern_confidence": "not-a-number",
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        with pytest.raises(ValueError, match="Invalid .codegraph.yml"):
            loader.load_config(tmp_path)

    def test_extra_fields_forbidden_raises_value_error(self, tmp_path: Path):
        """RepoConfig has extra='forbid', so unknown keys should fail."""
        cfg = {
            "schema_version": "2.0",
            "totally_unknown_field": True,
        }
        (tmp_path / ".codegraph.yml").write_text(yaml.dump(cfg))

        loader = YamlConfigLoader()
        with pytest.raises(ValueError, match="Invalid .codegraph.yml"):
            loader.load_config(tmp_path)


class TestMigrateV1ToV2Directly:
    """Direct tests for the _migrate_v1_to_v2 method."""

    def test_sets_schema_version(self):
        loader = YamlConfigLoader()
        result = loader._migrate_v1_to_v2({})
        assert result["schema_version"] == "2.0"

    def test_does_not_mutate_original(self):
        loader = YamlConfigLoader()
        original = {"detection_strategy": ["folder"]}
        result = loader._migrate_v1_to_v2(original)
        # Original should still have detection_strategy
        assert "detection_strategy" in original
        # Result should have detect_by instead
        assert "detect_by" in result
        assert "detection_strategy" not in result

    def test_layers_list_converted(self):
        loader = YamlConfigLoader()
        result = loader._migrate_v1_to_v2({"layers": ["a", "b"]})
        assert result["layers"] == {"a": ["**/*"], "b": ["**/*"]}

    def test_layers_dict_preserved(self):
        loader = YamlConfigLoader()
        layers = {"domain": ["src/**"]}
        result = loader._migrate_v1_to_v2({"layers": layers})
        assert result["layers"] == layers


class TestConfigInit:
    """Test that config __init__.py re-exports correctly."""

    def test_yaml_config_loader_importable(self):
        from coding_client.config import YamlConfigLoader as Imported

        assert Imported is YamlConfigLoader
