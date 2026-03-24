"""Tests for the Markdown specification extractor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sv0_mcp.extractors.markdown import MarkdownSpecExtractor
from sv0_mcp.models.base import EntityType, RelationType

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401


class TestMarkdownSpecExtractor:
    """Tests for MarkdownSpecExtractor against real sv0doc spec files."""

    def test_extract_type_rules(self, toolchain_root: Path) -> None:
        """Parsing type-system/rules.md should produce TypeRule entities."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        type_rules = [e for e in result.entities if e.entity_type == EntityType.TYPE_RULE]
        assert len(type_rules) > 0, "Expected at least one TypeRule entity"

        for rule in type_rules:
            assert rule.name, "Each TypeRule must have a name"
            assert rule.properties.get("section_number"), (
                f"TypeRule '{rule.name}' should have a section_number"
            )

    def test_extract_keywords(self, toolchain_root: Path) -> None:
        """Parsing keywords/reference.md should produce Keyword entities."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        keywords = [e for e in result.entities if e.entity_type == EntityType.KEYWORD]
        assert len(keywords) > 0, "Expected at least one Keyword entity"

        keyword_names = {e.name for e in keywords}
        expected_keywords = {"let", "fn", "if"}
        found = expected_keywords & keyword_names
        assert len(found) > 0, (
            f"Expected some common keywords like {expected_keywords}, got {keyword_names}"
        )

    def test_extract_operators(self, toolchain_root: Path) -> None:
        """Parsing keywords/reference.md should produce Operator entities."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        operators = [e for e in result.entities if e.entity_type == EntityType.OPERATOR]
        assert len(operators) > 0, "Expected at least one Operator entity"

        for op in operators:
            assert op.properties.get("symbol"), f"Operator '{op.name}' should have a symbol"

    def test_extract_contract_rules(self, toolchain_root: Path) -> None:
        """Parsing contracts/semantics.md should produce ContractRule entities."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        contract_rules = [e for e in result.entities if e.entity_type == EntityType.CONTRACT_RULE]
        assert len(contract_rules) > 0, "Expected at least one ContractRule entity"

        for rule in contract_rules:
            assert rule.name, "Each ContractRule must have a name"

    def test_extract_memory_rules(self, toolchain_root: Path) -> None:
        """Parsing memory-model/ownership.md should produce MemoryRule entities."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        memory_rules = [e for e in result.entities if e.entity_type == EntityType.MEMORY_RULE]
        assert len(memory_rules) > 0, "Expected at least one MemoryRule entity"

        for rule in memory_rules:
            assert rule.name, "Each MemoryRule must have a name"

    def test_specifies_relationships(self, toolchain_root: Path) -> None:
        """SPECIFIES relationships should link spec entities to compiler phases."""
        extractor = MarkdownSpecExtractor(toolchain_root)
        result = extractor.extract()

        specifies_rels = [
            r for r in result.relationships if r.relation_type == RelationType.SPECIFIES
        ]
        assert len(specifies_rels) > 0, "Expected at least one SPECIFIES relationship"

        targets = {r.target for r in specifies_rels}
        expected_targets = {"type_checker", "lexer", "parser", "contract_analyzer"}
        found = expected_targets & targets
        assert len(found) > 0, (
            f"Expected SPECIFIES targets among {expected_targets}, got {targets}"
        )
