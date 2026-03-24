"""Specialized models for sv0c compiler entities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from sv0_mcp.models.base import Entity, EntityType


class CompilerPhase(BaseModel):
    """A major phase of the sv0 compiler pipeline."""

    name: Literal[
        "lexer",
        "parser",
        "name_resolution",
        "type_checker",
        "contract_analyzer",
        "ir",
        "c_backend",
    ]
    description: str
    input_type: str
    output_type: str
    source_dir: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.COMPILER_PHASE,
            properties={
                "description": self.description,
                "input_type": self.input_type,
                "output_type": self.output_type,
                "source_dir": self.source_dir,
            },
        )


class CompilerModule(BaseModel):
    """A source module within a compiler phase."""

    name: str
    phase: str
    file_path: str | None = None
    description: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        properties = {
            "phase": self.phase,
            "description": self.description,
        }
        if self.file_path is not None:
            properties["file_path"] = self.file_path
        return Entity(
            name=self.name,
            entity_type=EntityType.COMPILER_MODULE,
            properties=properties,
        )
