"""Rmd task-file extractor for ``task/*.Rmd``."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from sv0_mcp.extractors.base import BaseExtractor, ExtractionResult
from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

_INCLUDE_RE = re.compile(r"^/include:\s*(.+)$", re.MULTILINE)
_REQUIRE_RE = re.compile(r"^/require:\s*(.+)$", re.MULTILINE)
_ASSERT_RE = re.compile(r"^/assert:\s*(.+)$", re.MULTILINE)
_ENV_RE = re.compile(r"^/env:\s*(.+)$", re.MULTILINE)
_PHASE_RE = re.compile(r"^## phase\s+(\d+):\s*(.+)$", re.MULTILINE | re.IGNORECASE)


class RmdExtractor(BaseExtractor):
    """Parse ``.Rmd`` task files in ``task/`` and extract task entities.

    Produces:
    - ``TASK`` or ``MILESTONE`` entities (based on the front-matter key).
    - ``INCLUDES`` relationships from milestones to child tasks.
    - ``DEPENDS_ON`` relationships derived from ``/require:`` directives.
    """

    def __init__(self, root_path: Path) -> None:
        """Initialise with the toolchain root.

        Args:
            root_path: Absolute path to the sv0-toolchain root directory.
        """
        super().__init__(root_path)
        self._task_dir = self.root_path / "task"

    def extract(self) -> ExtractionResult:
        """Scan ``task/`` for ``.Rmd`` files and extract task entities."""
        if not self._task_dir.is_dir():
            logger.warning("Task directory not found: %s", self._task_dir)
            return ExtractionResult()

        entities: list[Entity] = []
        relationships: list[Relationship] = []

        for rmd_path in sorted(self._task_dir.glob("*.Rmd")):
            self._extract_task(rmd_path, entities, relationships)

        return ExtractionResult(entities=entities, relationships=relationships)

    # ------------------------------------------------------------------
    # Per-file extraction
    # ------------------------------------------------------------------

    def _extract_task(
        self,
        path: Path,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Parse a single ``.Rmd`` file into entities and relationships."""
        text = path.read_text(encoding="utf-8")
        front_matter, body = _split_front_matter(text)

        task_key: str = front_matter.get("key", path.stem)
        is_milestone = "milestone" in task_key

        entity_type = EntityType.MILESTONE if is_milestone else EntityType.TASK
        properties: dict[str, Any] = {
            "id": front_matter.get("id", f"task-{task_key}"),
            "key": task_key,
            "state": front_matter.get("state", ""),
            "title": front_matter.get("title", ""),
            "type": front_matter.get("type", "task"),
            "created": str(front_matter.get("created", "")),
            "file": str(path.relative_to(self.root_path)),
        }
        tags = front_matter.get("tags")
        if isinstance(tags, list):
            properties["tags"] = tags

        observations: list[str] = []

        # /include: directives → INCLUDES relationships
        for match in _INCLUDE_RE.finditer(body):
            include_path = match.group(1).strip()
            target_key = Path(include_path).stem
            relationships.append(
                Relationship(
                    source=task_key,
                    target=target_key,
                    relation_type=RelationType.INCLUDES,
                )
            )

        # /require: directives → DEPENDS_ON + observation
        for match in _REQUIRE_RE.finditer(body):
            dep = match.group(1).strip()
            observations.append(f"requires: {dep}")
            relationships.append(
                Relationship(
                    source=task_key,
                    target=dep,
                    relation_type=RelationType.DEPENDS_ON,
                )
            )

        observations.extend(f"assert: {m.group(1).strip()}" for m in _ASSERT_RE.finditer(body))
        observations.extend(f"env: {m.group(1).strip()}" for m in _ENV_RE.finditer(body))
        observations.extend(
            f"phase {m.group(1)}: {m.group(2).strip()}" for m in _PHASE_RE.finditer(body)
        )

        entities.append(
            Entity(
                name=task_key,
                entity_type=entity_type,
                properties=properties,
                observations=observations,
            )
        )


# ======================================================================
# Module-level helpers
# ======================================================================


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from the body of an Rmd file.

    Returns:
        A ``(metadata_dict, body_text)`` tuple.  If no front matter
        is found, the metadata dict is empty and body is the full text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            yaml_str = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            data: dict[str, Any] = yaml.safe_load(yaml_str) or {}
            return data, body
    return {}, text
