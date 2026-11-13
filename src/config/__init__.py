"""Configuration loading for coding-client.

Provides YAML configuration loading with schema versioning support.
"""

from .base_settings import BaseMicroserviceSettings
from .yaml_config_loader import YamlConfigLoader

__all__ = [
    "BaseMicroserviceSettings",
    "YamlConfigLoader",
]
