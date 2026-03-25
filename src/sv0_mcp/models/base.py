"""Base entity and relationship models for the sv0-mcp knowledge graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """Classification of nodes in the sv0 knowledge graph."""

    GRAMMAR_PRODUCTION = "GrammarProduction"
    TYPE_RULE = "TypeRule"
    CONTRACT_RULE = "ContractRule"
    MEMORY_RULE = "MemoryRule"
    KEYWORD = "Keyword"
    OPERATOR = "Operator"
    PRIMITIVE_TYPE = "PrimitiveType"
    TRAIT_SPEC = "TraitSpec"
    DESIGN_DECISION = "DesignDecision"
    COMPILER_PHASE = "CompilerPhase"
    COMPILER_MODULE = "CompilerModule"
    AST_NODE = "AstNode"
    IR_CONSTRUCT = "IrConstruct"
    VM_COMPONENT = "VmComponent"
    VM_MODULE = "VmModule"
    TASK = "Task"
    MILESTONE = "Milestone"
    ROADMAP = "Roadmap"
    SOURCE_FILE = "SourceFile"
    DIRECTORY = "Directory"
    SUBPROJECT = "Subproject"


class RelationType(StrEnum):
    """Types of directed relationships between entities."""

    DEFINES = "DEFINES"
    IMPLEMENTS = "IMPLEMENTS"
    DEPENDS_ON = "DEPENDS_ON"
    CONTAINS = "CONTAINS"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    SPECIFIES = "SPECIFIES"
    REFERENCES = "REFERENCES"
    PART_OF = "PART_OF"
    PRECEDES = "PRECEDES"
    TRACES_TO = "TRACES_TO"
    INCLUDES = "INCLUDES"
    CHILD_OF = "CHILD_OF"


class Entity(BaseModel):
    """A node in the sv0 knowledge graph with typed properties and observations."""

    name: str
    entity_type: EntityType
    properties: dict[str, Any] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    """A directed, typed edge between two entities in the sv0 knowledge graph."""

    source: str
    target: str
    relation_type: RelationType
    properties: dict[str, Any] = Field(default_factory=dict)
