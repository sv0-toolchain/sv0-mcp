"""EBNF grammar extractor for ``sv0doc/grammar/sv0.ebnf``."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sv0_mcp.extractors.base import BaseExtractor, ExtractionResult
from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(r"\(\*\s*\d+\.\s+(.+?)\s*\*\)")
_PRODUCTION_START_RE = re.compile(r"^(\w+)\s*=")
_DESIGN_DECISION_RE = re.compile(r"\(\*\s*D(\d+):\s*(.+?)\s*\*\)")
_COMMENT_RE = re.compile(r"\(\*.*?\*\)")
_COMMENT_LINE_RE = re.compile(r"^\(\*\s*(.*?)\s*\*\)\s*$")


class EbnfExtractor(BaseExtractor):
    """Parse ``sv0doc/grammar/sv0.ebnf`` and extract grammar entities.

    Produces:
    - ``GRAMMAR_PRODUCTION`` entities for each EBNF production rule.
    - ``DESIGN_DECISION`` entities for each ``(* DN: … *)`` block.
    - ``CONTAINS`` relationships from the source file to each production.
    - ``REFERENCES`` relationships between productions that reference
      each other.
    """

    EBNF_RELATIVE = Path("sv0doc/grammar/sv0.ebnf")

    def __init__(self, root_path: Path) -> None:
        """Initialise with the toolchain root path.

        Args:
            root_path: Absolute path to the sv0-toolchain root directory.
        """
        super().__init__(root_path)
        self._ebnf_path = self.root_path / self.EBNF_RELATIVE

    def extract(self) -> ExtractionResult:
        """Parse the EBNF file and return grammar entities."""
        if not self._ebnf_path.is_file():
            logger.warning("EBNF file not found: %s", self._ebnf_path)
            return ExtractionResult()

        text = self._ebnf_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        source_name = str(self.EBNF_RELATIVE)
        source_entity = Entity(
            name=source_name,
            entity_type=EntityType.SOURCE_FILE,
            properties={"path": source_name, "language": "ebnf"},
        )

        productions = self._parse_productions(lines)
        decisions = self._parse_design_decisions(lines)

        entities: list[Entity] = [source_entity]
        relationships: list[Relationship] = []

        production_names = {name for name, _, _ in productions}

        for name, definition, section in productions:
            entities.append(
                Entity(
                    name=name,
                    entity_type=EntityType.GRAMMAR_PRODUCTION,
                    properties={"definition": definition, "section": section},
                )
            )
            relationships.append(
                Relationship(
                    source=source_name,
                    target=name,
                    relation_type=RelationType.CONTAINS,
                )
            )
            relationships.extend(
                Relationship(
                    source=name,
                    target=ref,
                    relation_type=RelationType.REFERENCES,
                )
                for ref in self._find_references(definition, production_names - {name})
            )

        for did, summary, rationale in decisions:
            entities.append(
                Entity(
                    name=f"D{did}",
                    entity_type=EntityType.DESIGN_DECISION,
                    properties={
                        "id": f"D{did}",
                        "summary": summary,
                        "rationale": rationale,
                    },
                )
            )

        return ExtractionResult(entities=entities, relationships=relationships)

    # ------------------------------------------------------------------
    # Production parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_productions(
        lines: list[str],
    ) -> list[tuple[str, str, str]]:
        """Parse production rules from EBNF lines.

        Returns:
            List of ``(name, definition, section)`` tuples.
        """
        productions: list[tuple[str, str, str]] = []
        current_section = ""
        i = 0
        while i < len(lines):
            line = lines[i]

            section_match = _SECTION_RE.search(line)
            if section_match:
                text = section_match.group(1).strip()
                if text == text.upper():
                    current_section = text.lower()
                i += 1
                continue

            prod_match = _PRODUCTION_START_RE.match(line)
            if prod_match:
                name = prod_match.group(1)
                definition_lines: list[str] = [line]
                while not definition_lines[-1].rstrip().endswith(";"):
                    i += 1
                    if i >= len(lines):
                        break
                    definition_lines.append(lines[i])

                raw = "\n".join(definition_lines)
                eq_idx = raw.index("=")
                raw_def = raw[eq_idx + 1 :]
                cleaned = _COMMENT_RE.sub("", raw_def).strip()
                if cleaned.endswith(";"):
                    cleaned = cleaned[:-1].strip()
                productions.append((name, cleaned, current_section))

            i += 1

        return productions

    # ------------------------------------------------------------------
    # Design-decision parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_design_decisions(
        lines: list[str],
    ) -> list[tuple[str, str, str]]:
        """Parse design-decision comment blocks.

        Returns:
            List of ``(id, summary, rationale)`` tuples.
        """
        decisions: list[tuple[str, str, str]] = []
        i = 0
        while i < len(lines):
            dd_match = _DESIGN_DECISION_RE.match(lines[i].strip())
            if dd_match:
                decision_id = dd_match.group(1)
                summary = dd_match.group(2).strip()
                rationale_parts: list[str] = []
                i += 1
                while i < len(lines):
                    cline = lines[i].strip()
                    if _DESIGN_DECISION_RE.match(cline):
                        break
                    comment_match = _COMMENT_LINE_RE.match(cline)
                    if not comment_match:
                        break
                    content = comment_match.group(1).strip()
                    if content:
                        rationale_parts.append(content)
                    i += 1
                decisions.append((decision_id, summary, " ".join(rationale_parts)))
                continue

            i += 1

        return decisions

    # ------------------------------------------------------------------
    # Cross-reference detection
    # ------------------------------------------------------------------

    @staticmethod
    def _find_references(
        definition: str,
        production_names: set[str],
    ) -> list[str]:
        """Find other production names referenced in *definition*.

        Quoted strings and EBNF prose (``? … ?``) are stripped before
        matching to prevent false positives.

        Returns:
            Sorted list of referenced production names.
        """
        if not production_names:
            return []
        cleaned = re.sub(r'"[^"]*"', "", definition)
        cleaned = re.sub(r"'[^']*'", "", cleaned)
        cleaned = re.sub(r"\?[^?]*\?", "", cleaned)
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(n) for n in sorted(production_names)) + r")\b"
        )
        return sorted(set(pattern.findall(cleaned)))
