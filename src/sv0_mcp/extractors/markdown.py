"""Markdown specification extractors for ``sv0doc/`` spec files.

Parses the following files into typed entities:

- ``type-system/rules.md``     → ``TYPE_RULE`` entities
- ``contracts/semantics.md``   → ``CONTRACT_RULE`` entities
- ``keywords/reference.md``    → ``KEYWORD`` and ``OPERATOR`` entities
- ``memory-model/ownership.md`` → ``MEMORY_RULE`` entities
"""

from __future__ import annotations

import logging
import re

from sv0_mcp.extractors.base import BaseExtractor, ExtractionResult
from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(r"^## (\d+)\.\s+(.+)$", re.MULTILINE)
_SUBSECTION_RE = re.compile(r"^### (\d+\.\d+)\s+(.+)$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")

_MIN_TABLE_COLS = 2
_ARITY_COL_IDX = 2
_TRAIT_COL_IDX = 3
_MIN_BACKTICK_LEN = 2

_CLAUSE_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("syntax", "syntax"),
    ("builtin", "builtin"),
    ("verification", "verification"),
    ("phase", "verification"),
    ("mode", "configuration"),
    ("setting", "configuration"),
    ("trait", "trait_interaction"),
    ("narrowing", "narrowing"),
    ("cast", "narrowing"),
]


class MarkdownSpecExtractor(BaseExtractor):
    """Parse markdown specification files in ``sv0doc/`` into entities.

    Produces ``SPECIFIES`` relationships from each spec entity to the
    compiler phase it specifies (e.g. ``TypeRule → type_checker``).
    """

    def extract(self) -> ExtractionResult:
        """Run all sub-extractors and merge their results."""
        result = ExtractionResult()
        for partial in [
            self._extract_type_rules(),
            self._extract_contract_rules(),
            self._extract_keywords(),
            self._extract_memory_rules(),
        ]:
            result = result.merge(partial)
        return result

    # ------------------------------------------------------------------
    # File-specific extractors
    # ------------------------------------------------------------------

    def _extract_type_rules(self) -> ExtractionResult:
        """Parse ``type-system/rules.md`` into ``TYPE_RULE`` entities."""
        return self._extract_subsection_entities(
            "type-system/rules.md",
            EntityType.TYPE_RULE,
            "type_checker",
        )

    def _extract_contract_rules(self) -> ExtractionResult:
        """Parse ``contracts/semantics.md`` into ``CONTRACT_RULE`` entities."""
        result = self._extract_subsection_entities(
            "contracts/semantics.md",
            EntityType.CONTRACT_RULE,
            "contract_analyzer",
        )
        for entity in result.entities:
            if entity.entity_type == EntityType.CONTRACT_RULE:
                category = entity.properties.get("category", "")
                entity.properties["clause_type"] = _infer_clause_type(category)
                entity.properties["scope"] = _infer_scope(entity.properties.get("description", ""))
        return result

    def _extract_memory_rules(self) -> ExtractionResult:
        """Parse ``memory-model/ownership.md`` into ``MEMORY_RULE`` entities."""
        return self._extract_subsection_entities(
            "memory-model/ownership.md",
            EntityType.MEMORY_RULE,
            "type_checker",
        )

    def _extract_keywords(self) -> ExtractionResult:
        """Parse ``keywords/reference.md`` into ``KEYWORD`` / ``OPERATOR``."""
        path = self.root_path / "sv0doc" / "keywords" / "reference.md"
        if not path.is_file():
            logger.warning("Keyword reference not found: %s", path)
            return ExtractionResult()

        text = path.read_text(encoding="utf-8")
        sections = _split_sections(text)

        entities: list[Entity] = []
        relationships: list[Relationship] = []

        for section_num, _section_title, section_body in sections:
            subsections = _split_subsections(section_body)
            for _sub_num, sub_title, sub_body in subsections:
                rows = _parse_table_rows(sub_body)
                if section_num == "1":
                    self._collect_keywords(rows, sub_title, entities, relationships)
                elif section_num == "2":
                    self._collect_operators(rows, sub_title, entities, relationships)

        return ExtractionResult(entities=entities, relationships=relationships)

    # ------------------------------------------------------------------
    # Keyword / operator helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_keywords(
        rows: list[list[str]],
        category: str,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Create ``KEYWORD`` entities from parsed table rows."""
        for row in rows:
            if len(row) < _MIN_TABLE_COLS:
                continue
            name = row[0]
            entities.append(
                Entity(
                    name=name,
                    entity_type=EntityType.KEYWORD,
                    properties={"purpose": row[1], "category": category},
                )
            )
            relationships.append(
                Relationship(
                    source=name,
                    target="lexer",
                    relation_type=RelationType.SPECIFIES,
                )
            )

    @staticmethod
    def _collect_operators(
        rows: list[list[str]],
        category: str,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Create ``OPERATOR`` entities from parsed table rows."""
        for row in rows:
            if len(row) < _MIN_TABLE_COLS:
                continue
            symbol = row[0]
            entities.append(
                Entity(
                    name=symbol,
                    entity_type=EntityType.OPERATOR,
                    properties={
                        "symbol": symbol,
                        "purpose": row[1],
                        "arity": (row[_ARITY_COL_IDX] if len(row) > _ARITY_COL_IDX else ""),
                        "trait_desugaring": (
                            row[_TRAIT_COL_IDX] if len(row) > _TRAIT_COL_IDX else ""
                        ),
                        "category": category,
                    },
                )
            )
            relationships.append(
                Relationship(
                    source=symbol,
                    target="parser",
                    relation_type=RelationType.SPECIFIES,
                )
            )

    # ------------------------------------------------------------------
    # Generic subsection → entity extraction
    # ------------------------------------------------------------------

    def _extract_subsection_entities(
        self,
        relative_path: str,
        entity_type: EntityType,
        phase_target: str,
    ) -> ExtractionResult:
        """Extract entities from a markdown file's subsection structure.

        Sections with no subsections produce a single entity for the
        whole section.

        Args:
            relative_path: Path relative to ``sv0doc/``.
            entity_type: Entity type to assign to each extracted entity.
            phase_target: Compiler phase name for ``SPECIFIES`` relationships.

        Returns:
            Extraction result with entities and relationships.
        """
        path = self.root_path / "sv0doc" / relative_path
        if not path.is_file():
            logger.warning("Spec file not found: %s", path)
            return ExtractionResult()

        text = path.read_text(encoding="utf-8")
        sections = _split_sections(text)

        entities: list[Entity] = []
        relationships: list[Relationship] = []

        for section_num, section_title, section_body in sections:
            subsections = _split_subsections(section_body)

            if not subsections:
                entities.append(
                    Entity(
                        name=section_title,
                        entity_type=entity_type,
                        properties={
                            "description": section_body,
                            "category": section_title,
                            "section_number": section_num,
                        },
                    )
                )
                relationships.append(
                    Relationship(
                        source=section_title,
                        target=phase_target,
                        relation_type=RelationType.SPECIFIES,
                    )
                )
                continue

            for sub_num, sub_title, sub_body in subsections:
                entities.append(
                    Entity(
                        name=sub_title,
                        entity_type=entity_type,
                        properties={
                            "description": sub_body,
                            "category": section_title,
                            "section_number": sub_num,
                        },
                    )
                )
                relationships.append(
                    Relationship(
                        source=sub_title,
                        target=phase_target,
                        relation_type=RelationType.SPECIFIES,
                    )
                )

        return ExtractionResult(entities=entities, relationships=relationships)


# ======================================================================
# Module-level helpers
# ======================================================================


def _split_sections(text: str) -> list[tuple[str, str, str]]:
    """Split markdown into ``(number, title, body)`` sections.

    Only ``## N. title`` headers are recognised.
    """
    matches = list(_SECTION_RE.finditer(text))
    sections: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((number, title, body))
    return sections


def _split_subsections(text: str) -> list[tuple[str, str, str]]:
    """Split section body into ``(number, title, body)`` subsections.

    Only ``### N.M title`` headers are recognised.
    """
    matches = list(_SUBSECTION_RE.finditer(text))
    subsections: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        subsections.append((number, title, body))
    return subsections


def _parse_table_rows(text: str) -> list[list[str]]:
    """Parse data rows from the first markdown table in *text*.

    Escaped pipes (``\\|``) inside cells are handled correctly.
    """
    rows: list[list[str]] = []
    past_separator = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if past_separator and stripped:
                break
            continue
        if _TABLE_SEP_RE.match(stripped):
            past_separator = True
            continue
        if past_separator:
            escaped = stripped.replace("\\|", "\x00")
            cells = [_clean_cell(c).replace("\x00", "|") for c in escaped.split("|")[1:-1]]
            rows.append(cells)
    return rows


def _clean_cell(raw: str) -> str:
    """Strip whitespace and optional surrounding backticks from a cell."""
    cell = raw.strip()
    if len(cell) >= _MIN_BACKTICK_LEN and cell.startswith("`") and cell.endswith("`"):
        return cell[1:-1]
    return cell


def _infer_clause_type(category: str) -> str:
    """Infer contract clause type from the section category name."""
    lower = category.lower()
    for keyword, clause_type in _CLAUSE_TYPE_KEYWORDS:
        if keyword in lower:
            return clause_type
    return "general"


def _infer_scope(description: str) -> str:
    """Infer contract scope from subsection description text."""
    lower = description.lower()
    if "loop_invariant" in lower or "loop invariant" in lower:
        return "loop"
    if "trait" in lower and "impl" in lower:
        return "trait"
    return "function"
