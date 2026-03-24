"""Specialized models for sv0vm virtual machine entities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from sv0_mcp.models.base import Entity, EntityType


class VmComponent(BaseModel):
    """A major component of the sv0 virtual machine."""

    name: Literal["bytecode", "interpreter", "runtime"]
    description: str
    source_dir: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.VM_COMPONENT,
            properties={
                "description": self.description,
                "source_dir": self.source_dir,
            },
        )


class VmModule(BaseModel):
    """A source module within a VM component."""

    name: str
    component: str
    file_path: str | None = None
    description: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        properties = {
            "component": self.component,
            "description": self.description,
        }
        if self.file_path is not None:
            properties["file_path"] = self.file_path
        return Entity(
            name=self.name,
            entity_type=EntityType.VM_MODULE,
            properties=properties,
        )
