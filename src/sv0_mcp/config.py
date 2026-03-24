"""Configuration management for sv0-mcp using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_TOOLCHAIN_ROOT = _PACKAGE_DIR.parent.parent.parent


class Sv0McpSettings(BaseSettings):
    """Central configuration for the sv0-mcp server and graph memory system.

    Reads from environment variables prefixed with ``SV0_MCP_``.
    Subproject root paths are derived automatically from ``toolchain_root``.
    """

    model_config = SettingsConfigDict(env_prefix="SV0_MCP_")

    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sv0-graph-dev"
    neo4j_database: str = "neo4j"
    toolchain_root: Path = _DEFAULT_TOOLCHAIN_ROOT
    sv0doc_root: Path = Path()
    sv0c_root: Path = Path()
    sv0vm_root: Path = Path()
    task_root: Path = Path()
    watch_debounce_seconds: float = 1.0
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _compute_derived_paths(self) -> Self:
        """Derive subproject root paths from ``toolchain_root``."""
        self.sv0doc_root = self.toolchain_root / "sv0doc"
        self.sv0c_root = self.toolchain_root / "sv0c"
        self.sv0vm_root = self.toolchain_root / "sv0vm"
        self.task_root = self.toolchain_root / "task"
        return self
