"""SML source-file extractor for ``sv0c/`` and ``sv0vm/``."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from sv0_mcp.extractors.base import BaseExtractor, ExtractionResult

if TYPE_CHECKING:
    from pathlib import Path
from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType

logger = logging.getLogger(__name__)

_STRUCTURE_RE = re.compile(r"^\s*structure\s+(\w+)", re.MULTILINE)
_SIGNATURE_RE = re.compile(r"^\s*signature\s+(\w+)", re.MULTILINE)
_FUN_RE = re.compile(r"^\s*fun\s+(\w+)", re.MULTILINE)
_VAL_RE = re.compile(r"^\s*val\s+(\w+)", re.MULTILINE)

_SML_EXTENSIONS = frozenset({".sml", ".sig", ".cm"})


class SmlExtractor(BaseExtractor):
    """Scan SML source files in a subproject and extract module entities.

    Since the SML source files may not exist yet (empty scaffolding),
    this extractor degrades gracefully and still produces directory
    structure entities when no source files are found.

    Args:
        root_path: Absolute path to the sv0-toolchain root.
        subproject: ``"sv0c"`` or ``"sv0vm"``.
    """

    def __init__(self, root_path: Path, subproject: str) -> None:
        """Initialise the extractor for a specific subproject.

        Args:
            root_path: Absolute path to the sv0-toolchain root directory.
            subproject: Subproject name — ``"sv0c"`` or ``"sv0vm"``.
        """
        super().__init__(root_path)
        self.subproject = subproject
        self._subproject_path = self.root_path / subproject

    def extract(self) -> ExtractionResult:
        """Scan for SML files and extract module entities."""
        if not self._subproject_path.is_dir():
            logger.warning("Subproject directory not found: %s", self._subproject_path)
            return ExtractionResult()

        entities: list[Entity] = []
        relationships: list[Relationship] = []

        sml_files = self._collect_sml_files()
        if not sml_files:
            logger.info(
                "No SML files found in %s — creating directory entities only",
                self.subproject,
            )
            self._add_directory_entities(entities, relationships)
            return ExtractionResult(entities=entities, relationships=relationships)

        for sml_path in sml_files:
            rel_path = str(sml_path.relative_to(self.root_path))
            file_entity = Entity(
                name=rel_path,
                entity_type=EntityType.SOURCE_FILE,
                properties={
                    "path": rel_path,
                    "language": "sml",
                    "subproject": self.subproject,
                },
            )
            entities.append(file_entity)

            if sml_path.suffix in {".sml", ".sig"}:
                try:
                    text = sml_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    logger.warning(
                        "Skipping non-UTF-8 SML path (unexpected outside .cm): %s",
                        rel_path,
                    )
                    continue
                self._parse_declarations(text, rel_path, entities, relationships)

        return ExtractionResult(entities=entities, relationships=relationships)

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_sml_files(self) -> list[Path]:
        """Return all SML/sig/cm files under the subproject, sorted.

        Skips paths under ``.cm/`` (SML/NJ Compilation Manager caches), which
        reuse ``.sml`` / ``.sig`` suffixes for binary artifacts and are not UTF-8
        text.
        """
        return sorted(
            p
            for p in self._subproject_path.rglob("*")
            if p.is_file()
            and p.suffix in _SML_EXTENSIONS
            and ".cm" not in p.parts
        )

    # ------------------------------------------------------------------
    # Declaration parsing
    # ------------------------------------------------------------------

    def _parse_declarations(
        self,
        text: str,
        source_file: str,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Parse SML declarations and create module entities / observations.

        ``structure`` declarations produce ``COMPILER_MODULE`` or
        ``VM_MODULE`` entities. ``signature``, ``fun``, and ``val``
        declarations are added as observations on the source-file entity.
        """
        module_type = (
            EntityType.COMPILER_MODULE if self.subproject == "sv0c" else EntityType.VM_MODULE
        )

        for match in _STRUCTURE_RE.finditer(text):
            struct_name = match.group(1)
            entities.append(
                Entity(
                    name=struct_name,
                    entity_type=module_type,
                    properties={
                        "source_file": source_file,
                        "subproject": self.subproject,
                    },
                )
            )
            relationships.append(
                Relationship(
                    source=source_file,
                    target=struct_name,
                    relation_type=RelationType.DEFINES,
                )
            )

        observations: list[str] = [f"signature {m.group(1)}" for m in _SIGNATURE_RE.finditer(text)]
        observations.extend(f"fun {m.group(1)}" for m in _FUN_RE.finditer(text))
        observations.extend(f"val {m.group(1)}" for m in _VAL_RE.finditer(text))

        if observations:
            for entity in entities:
                if entity.name == source_file and entity.entity_type == EntityType.SOURCE_FILE:
                    entity.observations.extend(observations)
                    break

    # ------------------------------------------------------------------
    # Directory fallback
    # ------------------------------------------------------------------

    def _add_directory_entities(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Create directory entities for existing directories in the subproject."""
        for child in sorted(self._subproject_path.iterdir()):
            if child.name.startswith(".") or not child.is_dir():
                continue
            rel = str(child.relative_to(self.root_path))
            entities.append(
                Entity(
                    name=rel,
                    entity_type=EntityType.DIRECTORY,
                    properties={"path": rel},
                )
            )
            relationships.append(
                Relationship(
                    source=rel,
                    target=self.subproject,
                    relation_type=RelationType.PART_OF,
                )
            )
