"""Models for task and workflow tracking entities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sv0_mcp.models.base import Entity, EntityType


class TaskEntry(BaseModel):
    """A tracked task in the sv0 development workflow."""

    key: str
    title: str
    state: Literal["draft", "in_progress", "done", "blocked"]
    tags: list[str] = Field(default_factory=list)
    source_file: str
    created: str | None = None

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        properties = {
            "title": self.title,
            "state": self.state,
            "tags": self.tags,
            "source_file": self.source_file,
        }
        if self.created is not None:
            properties["created"] = self.created
        return Entity(
            name=self.key,
            entity_type=EntityType.TASK,
            properties=properties,
        )


class MilestoneEntry(BaseModel):
    """A development milestone grouping related tasks."""

    key: str
    title: str
    description: str
    subproject: Literal["sv0doc", "sv0c", "sv0vm"]
    tasks: list[str] = Field(default_factory=list)

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.key,
            entity_type=EntityType.MILESTONE,
            properties={
                "title": self.title,
                "description": self.description,
                "subproject": self.subproject,
                "tasks": self.tasks,
            },
        )
