"""Tests for the graph synchronization engine with a mocked GraphClient."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from sv0_mcp.graph.sync import GraphSyncEngine, SyncResult, SyncScope
from sv0_mcp.models.base import EntityType, RelationType

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401

    from sv0_mcp.config import Sv0McpSettings

_SYNC_RESULT_ENTITIES_CREATED = 10
_SYNC_RESULT_ENTITIES_UPDATED = 5
_SYNC_RESULT_RELS_CREATED = 20
_SYNC_RESULT_DURATION = 1.5


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a fully mocked GraphClient that requires no Neo4j instance."""
    client = MagicMock()
    client.get_entity.return_value = None
    client.merge_entity.return_value = None
    client.merge_relationship.return_value = None
    client.get_all_entities.return_value = []
    return client


class TestSyncScopeEnum:
    """Tests for the SyncScope enumeration."""

    def test_sync_scope_values(self) -> None:
        """All expected SyncScope members should exist with correct string values."""
        expected = {
            "ALL": "all",
            "SPEC": "spec",
            "COMPILER": "compiler",
            "VM": "vm",
            "TASKS": "tasks",
            "STRUCTURE": "structure",
        }
        for member_name, member_value in expected.items():
            scope = SyncScope[member_name]
            assert scope.value == member_value, (
                f"SyncScope.{member_name} should be '{member_value}'"
            )

    def test_sync_scope_from_string(self) -> None:
        """SyncScope should be constructable from its string value."""
        assert SyncScope("all") == SyncScope.ALL
        assert SyncScope("spec") == SyncScope.SPEC


class TestSyncResultModel:
    """Tests for the SyncResult Pydantic model."""

    def test_sync_result_defaults(self) -> None:
        """SyncResult should have sensible zero/empty defaults."""
        result = SyncResult()

        assert result.entities_created == 0
        assert result.entities_updated == 0
        assert result.relationships_created == 0
        assert result.duration_seconds == 0.0
        assert result.scope == SyncScope.ALL
        assert result.errors == []

    def test_sync_result_with_values(self) -> None:
        """SyncResult should accept all fields."""
        result = SyncResult(
            entities_created=_SYNC_RESULT_ENTITIES_CREATED,
            entities_updated=_SYNC_RESULT_ENTITIES_UPDATED,
            relationships_created=_SYNC_RESULT_RELS_CREATED,
            duration_seconds=_SYNC_RESULT_DURATION,
            scope=SyncScope.SPEC,
            errors=["minor issue"],
        )

        assert result.entities_created == _SYNC_RESULT_ENTITIES_CREATED
        assert result.entities_updated == _SYNC_RESULT_ENTITIES_UPDATED
        assert result.relationships_created == _SYNC_RESULT_RELS_CREATED
        assert result.duration_seconds == _SYNC_RESULT_DURATION
        assert result.scope == SyncScope.SPEC
        assert result.errors == ["minor issue"]


class TestBuildTraceability:
    """Tests for the traceability relationship builder with a mocked GraphClient."""

    def test_build_traceability_grammar_productions(
        self,
        mock_client: MagicMock,
        settings: Sv0McpSettings,
    ) -> None:
        """Grammar productions should produce SPECIFIES relationships to lexer and parser."""
        mock_client.get_all_entities.side_effect = self._entities_by_type

        engine = GraphSyncEngine(client=mock_client, settings=settings)
        relationships = engine._build_traceability()

        grammar_rels = [
            r for r in relationships if r.source == "expr"
        ]
        targets = {r.target for r in grammar_rels}
        assert "lexer" in targets, "Grammar production should SPECIFIES lexer"
        assert "parser" in targets, "Grammar production should SPECIFIES parser"

    def test_build_traceability_type_rules(
        self,
        mock_client: MagicMock,
        settings: Sv0McpSettings,
    ) -> None:
        """Type rules should produce SPECIFIES relationships to type_checker."""
        mock_client.get_all_entities.side_effect = self._entities_by_type

        engine = GraphSyncEngine(client=mock_client, settings=settings)
        relationships = engine._build_traceability()

        type_rels = [r for r in relationships if r.source == "Numeric Widening"]
        targets = {r.target for r in type_rels}
        assert "type_checker" in targets, "TypeRule should SPECIFIES type_checker"

    def test_build_traceability_all_relation_types_are_specifies(
        self,
        mock_client: MagicMock,
        settings: Sv0McpSettings,
    ) -> None:
        """All traceability relationships should have SPECIFIES type."""
        mock_client.get_all_entities.side_effect = self._entities_by_type

        engine = GraphSyncEngine(client=mock_client, settings=settings)
        relationships = engine._build_traceability()

        for rel in relationships:
            assert rel.relation_type == RelationType.SPECIFIES, (
                f"Expected SPECIFIES, got {rel.relation_type} for {rel.source}->{rel.target}"
            )

    def test_build_traceability_empty_graph(
        self,
        mock_client: MagicMock,
        settings: Sv0McpSettings,
    ) -> None:
        """Traceability on an empty graph should produce no relationships."""
        mock_client.get_all_entities.return_value = []

        engine = GraphSyncEngine(client=mock_client, settings=settings)
        relationships = engine._build_traceability()

        assert relationships == []

    @staticmethod
    def _entities_by_type(entity_type: str | None = None) -> list[dict[str, str]]:
        """Return mock entities keyed by EntityType value."""
        mock_data: dict[str, list[dict[str, str]]] = {
            EntityType.GRAMMAR_PRODUCTION.value: [
                {"name": "expr", "entity_type": "GrammarProduction"},
                {"name": "stmt", "entity_type": "GrammarProduction"},
            ],
            EntityType.TYPE_RULE.value: [
                {"name": "Numeric Widening", "entity_type": "TypeRule"},
            ],
            EntityType.CONTRACT_RULE.value: [
                {"name": "Requires Clause", "entity_type": "ContractRule"},
            ],
            EntityType.MEMORY_RULE.value: [
                {"name": "Ownership Transfer", "entity_type": "MemoryRule"},
            ],
            EntityType.KEYWORD.value: [
                {"name": "let", "entity_type": "Keyword"},
            ],
            EntityType.OPERATOR.value: [
                {"name": "+", "entity_type": "Operator"},
            ],
        }
        return mock_data.get(entity_type or "", [])
