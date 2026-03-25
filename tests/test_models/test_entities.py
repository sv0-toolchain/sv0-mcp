"""Tests for the sv0-mcp domain model classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sv0_mcp.models.base import Entity, EntityType, Relationship, RelationType
from sv0_mcp.models.compiler import CompilerPhase
from sv0_mcp.models.spec import GrammarProduction
from sv0_mcp.models.workflow import TaskEntry

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401

EXPECTED_ENTITY_TYPE_COUNT = 21
EXPECTED_RELATION_TYPE_COUNT = 13


class TestEntity:
    """Tests for the Entity base model."""

    def test_entity_creation(self) -> None:
        """Entity should be created with all fields populated."""
        entity = Entity(
            name="test_entity",
            entity_type=EntityType.GRAMMAR_PRODUCTION,
            properties={"definition": "a | b", "section": "expressions"},
            observations=["source: grammar.ebnf"],
        )

        assert entity.name == "test_entity"
        assert entity.entity_type == EntityType.GRAMMAR_PRODUCTION
        assert entity.properties["definition"] == "a | b"
        assert entity.observations == ["source: grammar.ebnf"]

    def test_entity_defaults(self) -> None:
        """Entity should default to empty properties and observations."""
        entity = Entity(name="minimal", entity_type=EntityType.TASK)

        assert entity.properties == {}
        assert entity.observations == []


class TestRelationship:
    """Tests for the Relationship model."""

    def test_relationship_creation(self) -> None:
        """Relationship should be created with source, target, and type."""
        rel = Relationship(
            source="lexer",
            target="parser",
            relation_type=RelationType.PRECEDES,
            properties={"order": 1},
        )

        assert rel.source == "lexer"
        assert rel.target == "parser"
        assert rel.relation_type == RelationType.PRECEDES
        assert rel.properties["order"] == 1

    def test_relationship_defaults(self) -> None:
        """Relationship should default to empty properties."""
        rel = Relationship(
            source="a",
            target="b",
            relation_type=RelationType.DEFINES,
        )

        assert rel.properties == {}


class TestEntityTypeEnum:
    """Tests for the EntityType enumeration."""

    def test_entity_type_values(self) -> None:
        """All expected EntityType members should exist."""
        expected_members = {
            "GRAMMAR_PRODUCTION",
            "TYPE_RULE",
            "CONTRACT_RULE",
            "MEMORY_RULE",
            "KEYWORD",
            "OPERATOR",
            "PRIMITIVE_TYPE",
            "TRAIT_SPEC",
            "DESIGN_DECISION",
            "COMPILER_PHASE",
            "COMPILER_MODULE",
            "AST_NODE",
            "IR_CONSTRUCT",
            "VM_COMPONENT",
            "VM_MODULE",
            "TASK",
            "MILESTONE",
            "ROADMAP",
            "SOURCE_FILE",
            "DIRECTORY",
            "SUBPROJECT",
        }
        actual_members = {member.name for member in EntityType}
        assert expected_members == actual_members
        assert len(actual_members) == EXPECTED_ENTITY_TYPE_COUNT

    def test_entity_type_is_str_enum(self) -> None:
        """EntityType members should be usable as strings."""
        assert str(EntityType.GRAMMAR_PRODUCTION) == "GrammarProduction"
        assert EntityType.GRAMMAR_PRODUCTION.value == "GrammarProduction"


class TestRelationTypeEnum:
    """Tests for the RelationType enumeration."""

    def test_relation_type_values(self) -> None:
        """All expected RelationType members should exist."""
        expected_members = {
            "DEFINES",
            "IMPLEMENTS",
            "DEPENDS_ON",
            "CONTAINS",
            "PRODUCES",
            "CONSUMES",
            "SPECIFIES",
            "REFERENCES",
            "PART_OF",
            "PRECEDES",
            "TRACES_TO",
            "INCLUDES",
            "CHILD_OF",
        }
        actual_members = {member.name for member in RelationType}
        assert expected_members == actual_members
        assert len(actual_members) == EXPECTED_RELATION_TYPE_COUNT

    def test_relation_type_is_str_enum(self) -> None:
        """RelationType members should be usable as strings."""
        assert RelationType.PRECEDES.value == "PRECEDES"


class TestGrammarProductionToEntity:
    """Tests for GrammarProduction.to_entity() conversion."""

    def test_grammar_production_to_entity(self) -> None:
        """GrammarProduction.to_entity() should produce a valid Entity."""
        prod = GrammarProduction(
            name="expr",
            definition="term { '+' term }",
            section="expressions",
            source_file="sv0doc/grammar/sv0.ebnf",
        )
        entity = prod.to_entity()

        assert entity.name == "expr"
        assert entity.entity_type == EntityType.GRAMMAR_PRODUCTION
        assert entity.properties["definition"] == "term { '+' term }"
        assert entity.properties["section"] == "expressions"
        assert entity.properties["source_file"] == "sv0doc/grammar/sv0.ebnf"


class TestTaskEntryToEntity:
    """Tests for TaskEntry.to_entity() conversion."""

    def test_task_entry_to_entity(self) -> None:
        """TaskEntry.to_entity() should produce a Task entity keyed by key."""
        task = TaskEntry(
            key="sv0c-lexer",
            title="Implement Lexer",
            state="in_progress",
            tags=["compiler", "lexer"],
            source_file="task/sv0c-lexer.Rmd",
            created="2025-06-01",
        )
        entity = task.to_entity()

        assert entity.name == "sv0c-lexer"
        assert entity.entity_type == EntityType.TASK
        assert entity.properties["title"] == "Implement Lexer"
        assert entity.properties["state"] == "in_progress"
        assert entity.properties["tags"] == ["compiler", "lexer"]
        assert entity.properties["created"] == "2025-06-01"

    def test_task_entry_without_optional_fields(self) -> None:
        """TaskEntry.to_entity() should omit created when not provided."""
        task = TaskEntry(
            key="minimal-task",
            title="Minimal",
            state="draft",
            source_file="task/minimal.Rmd",
        )
        entity = task.to_entity()

        assert entity.name == "minimal-task"
        assert "created" not in entity.properties


class TestCompilerPhaseToEntity:
    """Tests for CompilerPhase.to_entity() conversion."""

    def test_compiler_phase_to_entity(self) -> None:
        """CompilerPhase.to_entity() should produce a CompilerPhase entity."""
        phase = CompilerPhase(
            name="lexer",
            description="Tokenizes source text",
            input_type="source text",
            output_type="token stream",
            source_dir="sv0c/src/lexer",
        )
        entity = phase.to_entity()

        assert entity.name == "lexer"
        assert entity.entity_type == EntityType.COMPILER_PHASE
        assert entity.properties["input_type"] == "source text"
        assert entity.properties["output_type"] == "token stream"
        assert entity.properties["source_dir"] == "sv0c/src/lexer"
