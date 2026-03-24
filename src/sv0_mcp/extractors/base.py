"""Abstract base extractor and extraction result container."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from sv0_mcp.models.base import Entity, Relationship

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class ExtractionResult(BaseModel):
    """Container for entities and relationships produced by an extractor.

    Two results can be combined via :meth:`merge` to aggregate output from
    multiple extraction passes.
    """

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    def merge(self, other: ExtractionResult) -> ExtractionResult:
        """Return a new result combining this result with *other*.

        Args:
            other: The extraction result to merge into a combined result.

        Returns:
            A new ``ExtractionResult`` with concatenated entity and
            relationship lists.
        """
        return ExtractionResult(
            entities=[*self.entities, *other.entities],
            relationships=[*self.relationships, *other.relationships],
        )


class BaseExtractor(ABC):
    """Abstract base class for sv0-toolchain source extractors.

    Subclasses parse specific file formats under the toolchain root and
    produce ``Entity`` / ``Relationship`` objects collected into an
    ``ExtractionResult``.
    """

    def __init__(self, root_path: Path) -> None:
        """Initialise the extractor.

        Args:
            root_path: Absolute path to the sv0-toolchain root directory.
        """
        self.root_path = root_path

    @abstractmethod
    def extract(self) -> ExtractionResult:
        """Run extraction and return discovered entities and relationships."""
        ...
