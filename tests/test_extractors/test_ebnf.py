"""Tests for the EBNF grammar extractor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sv0_mcp.extractors.ebnf import EbnfExtractor
from sv0_mcp.models.base import EntityType, RelationType

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401


class TestEbnfExtractor:
    """Tests for EbnfExtractor against the real sv0.ebnf file."""

    def test_extract_productions(self, toolchain_root: Path) -> None:
        """Parsing the real sv0.ebnf should produce GrammarProduction entities."""
        extractor = EbnfExtractor(toolchain_root)
        result = extractor.extract()

        production_entities = [
            e for e in result.entities if e.entity_type == EntityType.GRAMMAR_PRODUCTION
        ]
        assert len(production_entities) > 0, "Expected at least one GrammarProduction entity"

        names = {e.name for e in production_entities}
        assert "expr" in names or any(
            "expr" in n for n in names
        ), "Expected an expression-related production"

    def test_extract_design_decisions(self, toolchain_root: Path) -> None:
        """D1 through D17 design decisions should be extracted from the EBNF file."""
        extractor = EbnfExtractor(toolchain_root)
        result = extractor.extract()

        decision_entities = [
            e for e in result.entities if e.entity_type == EntityType.DESIGN_DECISION
        ]
        assert len(decision_entities) > 0, "Expected at least one DesignDecision entity"

        decision_ids = {e.name for e in decision_entities}
        assert "D1" in decision_ids, "Expected design decision D1"

        for entity in decision_entities:
            assert entity.properties.get("summary"), (
                f"Decision {entity.name} should have a summary"
            )

    def test_extract_references(self, toolchain_root: Path) -> None:
        """REFERENCES relationships should link productions that reference each other."""
        extractor = EbnfExtractor(toolchain_root)
        result = extractor.extract()

        ref_rels = [r for r in result.relationships if r.relation_type == RelationType.REFERENCES]
        assert len(ref_rels) > 0, "Expected at least one REFERENCES relationship"

        sources = {r.source for r in ref_rels}
        targets = {r.target for r in ref_rels}
        assert len(sources) > 1, "Multiple productions should reference others"
        assert len(targets) > 1, "Multiple productions should be referenced"

    def test_missing_file(self, tmp_path: Path) -> None:
        """Extractor should return empty result when the EBNF file is absent."""
        extractor = EbnfExtractor(tmp_path)
        result = extractor.extract()

        assert len(result.entities) == 0
        assert len(result.relationships) == 0
