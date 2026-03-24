"""Directory-structure extractor and compiler-pipeline builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sv0_mcp.extractors.base import BaseExtractor, ExtractionResult

if TYPE_CHECKING:
    from pathlib import Path
from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType

logger = logging.getLogger(__name__)

_SUBPROJECTS: dict[str, str] = {
    "sv0doc": "formal language specification (source of truth)",
    "sv0c": "bootstrap compiler in SML/NJ",
    "sv0vm": "bytecode VM interpreter in SML/NJ",
}

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".cursor",
        ".agent",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
    }
)

_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".ebnf", ".sml", ".sig", ".cm", ".Rmd", ".toml", ".txt"}
)

_COMPILER_PHASES: list[tuple[str, str, str, str]] = [
    ("lexer", "source text", "token stream", "sv0c/src/lexer"),
    ("parser", "token stream", "untyped AST", "sv0c/src/parser"),
    (
        "name_resolution",
        "untyped AST",
        "resolved AST",
        "sv0c/src/name_resolution",
    ),
    (
        "type_checker",
        "resolved AST",
        "typed AST",
        "sv0c/src/type_checker",
    ),
    (
        "contract_analyzer",
        "typed AST",
        "annotated AST",
        "sv0c/src/contract_analyzer",
    ),
    ("ir", "annotated AST", "sv0-IR", "sv0c/src/ir"),
    ("c_backend", "sv0-IR", "C source", "sv0c/src/backend/c"),
]

_VM_COMPONENTS: list[tuple[str, str]] = [
    ("bytecode", "bytecode format definition"),
    ("interpreter", "bytecode execution engine"),
    ("runtime", "memory and stack management"),
]


class DirectoryExtractor(BaseExtractor):
    """Scan the directory structure and create project-level entities.

    Produces:
    - ``SUBPROJECT`` entities for sv0doc, sv0c, sv0vm.
    - ``DIRECTORY`` entities for each significant directory.
    - ``SOURCE_FILE`` entities for key files.
    - ``CONTAINS`` / ``PART_OF`` relationships.
    - ``COMPILER_PHASE`` entities with ``PRECEDES``, ``CONSUMES``, and
      ``PRODUCES`` relationships.
    - ``VM_COMPONENT`` entities with ``PRECEDES`` relationships.
    """

    def extract(self) -> ExtractionResult:
        """Scan the workspace and build the project graph."""
        entities: list[Entity] = []
        relationships: list[Relationship] = []

        self._create_subproject_entities(entities)
        self._scan_directories(entities, relationships)
        self._create_compiler_pipeline(entities, relationships)
        self._create_vm_components(entities, relationships)

        return ExtractionResult(entities=entities, relationships=relationships)

    # ------------------------------------------------------------------
    # Subproject entities
    # ------------------------------------------------------------------

    @staticmethod
    def _create_subproject_entities(entities: list[Entity]) -> None:
        """Create a ``SUBPROJECT`` entity for each known subproject."""
        for name, description in _SUBPROJECTS.items():
            entities.append(
                Entity(
                    name=name,
                    entity_type=EntityType.SUBPROJECT,
                    properties={"description": description, "path": name},
                )
            )

    # ------------------------------------------------------------------
    # Directory / file scanning
    # ------------------------------------------------------------------

    def _scan_directories(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Walk each subproject and create directory/file entities."""
        for subproject in _SUBPROJECTS:
            subproject_path = self.root_path / subproject
            if not subproject_path.is_dir():
                continue
            self._walk_directory(
                subproject_path,
                subproject,
                entities,
                relationships,
                is_root=True,
            )

    def _walk_directory(
        self,
        dir_path: Path,
        subproject: str,
        entities: list[Entity],
        relationships: list[Relationship],
        *,
        is_root: bool = False,
    ) -> None:
        """Recursively create entities for a directory tree.

        Args:
            dir_path: Directory to scan.
            subproject: Owning subproject name (for ``PART_OF``).
            entities: Accumulator for new entities.
            relationships: Accumulator for new relationships.
            is_root: If ``True``, skip creating a ``DIRECTORY`` entity
                for *dir_path* itself (the subproject entity already
                represents it).
        """
        rel_path = str(dir_path.relative_to(self.root_path))
        parent_name = subproject if is_root else rel_path

        if not is_root:
            entities.append(
                Entity(
                    name=rel_path,
                    entity_type=EntityType.DIRECTORY,
                    properties={"path": rel_path},
                )
            )
            relationships.append(
                Relationship(
                    source=rel_path,
                    target=subproject,
                    relation_type=RelationType.PART_OF,
                )
            )

        try:
            children = sorted(dir_path.iterdir())
        except PermissionError:
            logger.debug("Permission denied: %s", dir_path)
            return

        for child in children:
            if child.name in _SKIP_DIRS or child.name.startswith("."):
                continue

            if child.is_dir():
                child_rel = str(child.relative_to(self.root_path))
                relationships.append(
                    Relationship(
                        source=parent_name,
                        target=child_rel,
                        relation_type=RelationType.CONTAINS,
                    )
                )
                self._walk_directory(child, subproject, entities, relationships)
            elif child.is_file() and child.suffix in _SOURCE_EXTENSIONS:
                file_rel = str(child.relative_to(self.root_path))
                entities.append(
                    Entity(
                        name=file_rel,
                        entity_type=EntityType.SOURCE_FILE,
                        properties={
                            "path": file_rel,
                            "extension": child.suffix,
                            "subproject": subproject,
                        },
                    )
                )
                relationships.append(
                    Relationship(
                        source=parent_name,
                        target=file_rel,
                        relation_type=RelationType.CONTAINS,
                    )
                )
                relationships.append(
                    Relationship(
                        source=file_rel,
                        target=subproject,
                        relation_type=RelationType.PART_OF,
                    )
                )

    # ------------------------------------------------------------------
    # Compiler pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _create_compiler_pipeline(
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Create ``COMPILER_PHASE`` entities and pipeline relationships.

        Each phase gets ``PRECEDES``, ``CONSUMES``, and ``PRODUCES``
        relationships describing the data flow through the compiler.
        """
        for i, (name, input_type, output_type, source_dir) in enumerate(_COMPILER_PHASES):
            entities.append(
                Entity(
                    name=name,
                    entity_type=EntityType.COMPILER_PHASE,
                    properties={
                        "input_type": input_type,
                        "output_type": output_type,
                        "source_directory": source_dir,
                        "order": i,
                    },
                )
            )
            relationships.append(
                Relationship(
                    source=name,
                    target=input_type,
                    relation_type=RelationType.CONSUMES,
                )
            )
            relationships.append(
                Relationship(
                    source=name,
                    target=output_type,
                    relation_type=RelationType.PRODUCES,
                )
            )
            if i > 0:
                prev_name = _COMPILER_PHASES[i - 1][0]
                relationships.append(
                    Relationship(
                        source=prev_name,
                        target=name,
                        relation_type=RelationType.PRECEDES,
                    )
                )

    # ------------------------------------------------------------------
    # VM components
    # ------------------------------------------------------------------

    @staticmethod
    def _create_vm_components(
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Create ``VM_COMPONENT`` entities with ``PRECEDES`` ordering."""
        for i, (name, description) in enumerate(_VM_COMPONENTS):
            entities.append(
                Entity(
                    name=name,
                    entity_type=EntityType.VM_COMPONENT,
                    properties={"description": description, "order": i},
                )
            )
            if i > 0:
                prev_name = _VM_COMPONENTS[i - 1][0]
                relationships.append(
                    Relationship(
                        source=prev_name,
                        target=name,
                        relation_type=RelationType.PRECEDES,
                    )
                )
