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

# Task Rmd front-matter keys we may auto-fix when `:` is missing a space (`state:done`).
_KNOWN_FM_KEYS = frozenset({
    "created",
    "graph_entity_type",
    "id",
    "key",
    "roadmap_parent",
    "state",
    "tags",
    "title",
    "type",
    "updated",
})
_LINE_MISSING_SPACE_AFTER_COLON = re.compile(
    r"^(?P<prefix>\s*)(?P<key>[a-zA-Z0-9_]+):(?P<rest>\S.*)$",
)


class RmdExtractor(BaseExtractor):
    """Parse ``.Rmd`` task files in ``task/`` and extract task entities.

    Produces:
    - ``TASK``, ``MILESTONE``, or ``ROADMAP`` entities (see below).
    - ``INCLUDES`` relationships from milestones to child tasks.
    - ``DEPENDS_ON`` relationships derived from ``/require:`` directives.
    - ``PART_OF`` from a task/milestone to a roadmap when ``roadmap_parent`` is set.

    Entity kind:
    - Optional YAML ``graph_entity_type``: ``task`` | ``milestone`` | ``roadmap``
      (overrides the default heuristic).
    - Default: ``MILESTONE`` if ``milestone`` appears in the task ``key``,
      otherwise ``TASK``.
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
            try:
                self._extract_task(rmd_path, entities, relationships)
            except Exception:
                logger.exception(
                    "Skipping task file (parse error): %s",
                    rmd_path,
                )

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
        entity_type = _entity_type_from_front_matter(
            front_matter,
            task_key,
        )
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
        updated = front_matter.get("updated")
        if updated is not None:
            properties["updated"] = str(updated)

        observations: list[str] = []

        roadmap_parent = front_matter.get("roadmap_parent")
        if isinstance(roadmap_parent, str) and roadmap_parent.strip():
            relationships.append(
                Relationship(
                    source=task_key,
                    target=roadmap_parent.strip(),
                    relation_type=RelationType.PART_OF,
                )
            )

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


def _entity_type_from_front_matter(
    front_matter: dict[str, Any],
    task_key: str,
) -> EntityType:
    """Resolve graph entity type from YAML or key heuristic."""
    raw = front_matter.get("graph_entity_type")
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered == "roadmap":
            return EntityType.ROADMAP
        if lowered == "milestone":
            return EntityType.MILESTONE
        if lowered == "task":
            return EntityType.TASK
    if "milestone" in task_key:
        return EntityType.MILESTONE
    return EntityType.TASK


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
            yaml_str = _normalize_front_matter_yaml(yaml_str)
            data: dict[str, Any] = yaml.safe_load(yaml_str) or {}
            return data, body
    return {}, text


def _normalize_front_matter_yaml(yaml_str: str) -> str:
    """Insert a space after ``:`` for known keys when authors omit it (``state:done``)."""
    out_lines: list[str] = []
    for line in yaml_str.splitlines():
        m = _LINE_MISSING_SPACE_AFTER_COLON.match(line)
        if m and m.group("key") in _KNOWN_FM_KEYS:
            out_lines.append(
                f"{m.group('prefix')}{m.group('key')}: {m.group('rest')}",
            )
        else:
            out_lines.append(line)
    return "\n".join(out_lines)
