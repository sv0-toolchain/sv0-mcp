"""Graph synchronization engine for the sv0 toolchain."""

from __future__ import annotations

import logging
import time
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from sv0_mcp.extractors.directory import DirectoryExtractor
from sv0_mcp.extractors.ebnf import EbnfExtractor
from sv0_mcp.extractors.markdown import MarkdownSpecExtractor
from sv0_mcp.extractors.rmd import RmdExtractor
from sv0_mcp.extractors.sml import SmlExtractor
from sv0_mcp.models.base import EntityType, Relationship, RelationType

if TYPE_CHECKING:
    from collections.abc import Callable

    from sv0_mcp.config import Sv0McpSettings
    from sv0_mcp.extractors.base import ExtractionResult
    from sv0_mcp.graph.client import GraphClient

logger = logging.getLogger(__name__)


class SyncScope(StrEnum):
    """Scope for graph synchronization operations."""

    ALL = "all"
    SPEC = "spec"
    COMPILER = "compiler"
    VM = "vm"
    TASKS = "tasks"
    STRUCTURE = "structure"


class SyncResult(BaseModel):
    """Result of a graph synchronization operation."""

    entities_created: int = 0
    entities_updated: int = 0
    relationships_created: int = 0
    duration_seconds: float = 0.0
    scope: SyncScope = SyncScope.ALL
    errors: list[str] = Field(default_factory=list)


class GraphSyncEngine:
    """Orchestrates extraction and graph synchronization."""

    def __init__(
        self,
        client: GraphClient,
        settings: Sv0McpSettings,
    ) -> None:
        """Initialize the sync engine.

        Args:
            client: Graph client for database operations.
            settings: Application settings with project paths.
        """
        self._client = client
        self._settings = settings

    def sync(
        self,
        scope: SyncScope = SyncScope.ALL,
    ) -> SyncResult:
        """Run a full sync for the given scope.

        1. Run the appropriate extractors based on scope.
        2. Merge all entities and relationships into the graph.
        3. Return the sync result with counts.

        Args:
            scope: Which portion of the toolchain to sync.

        Returns:
            Sync result with entity and relationship counts.
        """
        start = time.monotonic()
        result = SyncResult(scope=scope)
        scope_handlers: dict[
            SyncScope,
            list[Callable[[], ExtractionResult]],
        ] = {
            SyncScope.SPEC: [self._sync_spec],
            SyncScope.COMPILER: [self._sync_compiler],
            SyncScope.VM: [self._sync_vm],
            SyncScope.TASKS: [self._sync_tasks],
            SyncScope.STRUCTURE: [self._sync_structure],
            SyncScope.ALL: [
                self._sync_spec,
                self._sync_compiler,
                self._sync_vm,
                self._sync_tasks,
                self._sync_structure,
            ],
        }
        handlers = scope_handlers.get(scope, [])
        for handler in handlers:
            try:
                extraction = handler()
            except Exception as exc:
                result.errors.append(
                    f"{handler.__name__}: {exc}"
                )
                continue
            created, updated, rels = (
                self._apply_extraction(extraction)
            )
            result.entities_created += created
            result.entities_updated += updated
            result.relationships_created += rels
        if scope == SyncScope.ALL:
            self._apply_traceability(result)
        result.duration_seconds = time.monotonic() - start
        logger.info(
            "Sync complete (%s): %d created, "
            "%d updated, %d rels in %.2fs",
            scope.value,
            result.entities_created,
            result.entities_updated,
            result.relationships_created,
            result.duration_seconds,
        )
        return result

    # ------------------------------------------------------------------
    # Per-scope extractors
    # ------------------------------------------------------------------

    def _sync_spec(self) -> ExtractionResult:
        """Extract and sync sv0doc specification entities."""
        root = self._settings.toolchain_root
        ebnf = EbnfExtractor(root)
        md = MarkdownSpecExtractor(root)
        return ebnf.extract().merge(md.extract())

    def _sync_compiler(self) -> ExtractionResult:
        """Extract and sync sv0c compiler entities."""
        root = self._settings.toolchain_root
        extractor = SmlExtractor(root, subproject="sv0c")
        return extractor.extract()

    def _sync_vm(self) -> ExtractionResult:
        """Extract and sync sv0vm entities."""
        root = self._settings.toolchain_root
        extractor = SmlExtractor(root, subproject="sv0vm")
        return extractor.extract()

    def _sync_tasks(self) -> ExtractionResult:
        """Extract and sync task/workflow entities."""
        extractor = RmdExtractor(self._settings.toolchain_root)
        return extractor.extract()

    def _sync_structure(self) -> ExtractionResult:
        """Extract and sync directory structure entities."""
        extractor = DirectoryExtractor(
            self._settings.toolchain_root,
        )
        return extractor.extract()

    # ------------------------------------------------------------------
    # Application helpers
    # ------------------------------------------------------------------

    def _apply_extraction(
        self,
        result: ExtractionResult,
    ) -> tuple[int, int, int]:
        """Apply an ExtractionResult to the graph.

        Returns:
            Tuple of ``(entities_created, entities_updated,
            relationships_created)``.
        """
        created = 0
        updated = 0
        rels = 0
        for entity in result.entities:
            c, u = self._merge_entity_safe(entity)
            created += c
            updated += u
        for relationship in result.relationships:
            if self._merge_relationship_safe(relationship):
                rels += 1
        return created, updated, rels

    def _merge_entity_safe(
        self,
        entity: object,
    ) -> tuple[int, int]:
        """Merge a single entity, catching errors.

        Returns:
            ``(1, 0)`` if created, ``(0, 1)`` if updated,
            or ``(0, 0)`` on failure.
        """
        try:
            name: str = entity.name  # type: ignore[attr-defined]
            existing = self._client.get_entity(name)
            self._client.merge_entity(entity)  # type: ignore[arg-type]
        except Exception:
            logger.exception(
                "Failed to merge entity %s",
                getattr(entity, "name", "<unknown>"),
            )
            return 0, 0
        return (0, 1) if existing else (1, 0)

    def _merge_relationship_safe(
        self,
        relationship: object,
    ) -> bool:
        """Merge a single relationship, catching errors.

        Returns:
            ``True`` on success.
        """
        try:
            self._client.merge_relationship(relationship)  # type: ignore[arg-type]
        except Exception:
            logger.exception(
                "Failed to merge relationship %s->%s",
                getattr(relationship, "source", "?"),
                getattr(relationship, "target", "?"),
            )
            return False
        return True

    def _apply_traceability(
        self,
        result: SyncResult,
    ) -> None:
        """Apply traceability relationships and update *result*."""
        traceability = self._build_traceability()
        for rel in traceability:
            if self._merge_relationship_safe(rel):
                result.relationships_created += 1
            else:
                result.errors.append(
                    f"Traceability {rel.source}"
                    f"->{rel.target}: merge failed"
                )

    def _build_traceability(self) -> list[Relationship]:
        """Build cross-cutting traceability relationships.

        Creates ``SPECIFIES`` relationships between:

        * Grammar productions and lexer / parser phases
        * Type rules and the type_checker phase
        * Contract rules and the contract_analyzer phase
        * Memory rules and type_checker / contract_analyzer
        * Keywords and the lexer phase
        * Operators and lexer / parser phases
        """
        type_phase_map: dict[str, list[str]] = {
            EntityType.GRAMMAR_PRODUCTION.value: [
                "lexer",
                "parser",
            ],
            EntityType.TYPE_RULE.value: [
                "type_checker",
            ],
            EntityType.CONTRACT_RULE.value: [
                "contract_analyzer",
            ],
            EntityType.MEMORY_RULE.value: [
                "type_checker",
                "contract_analyzer",
            ],
            EntityType.KEYWORD.value: ["lexer"],
            EntityType.OPERATOR.value: [
                "lexer",
                "parser",
            ],
        }
        relationships: list[Relationship] = []
        for entity_type, phases in type_phase_map.items():
            entities = self._client.get_all_entities(
                entity_type,
            )
            for entity in entities:
                name = entity.get("name", "")
                if not name:
                    continue
                relationships.extend(
                    Relationship(
                        source=name,
                        target=phase,
                        relation_type=RelationType.SPECIFIES,
                    )
                    for phase in phases
                )
        return relationships
