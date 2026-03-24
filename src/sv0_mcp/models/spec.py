"""Specialized models for sv0doc language specification entities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sv0_mcp.models.base import Entity, EntityType


class GrammarProduction(BaseModel):
    """A grammar production rule from the sv0 language specification."""

    name: str
    definition: str
    section: str
    source_file: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.GRAMMAR_PRODUCTION,
            properties={
                "definition": self.definition,
                "section": self.section,
                "source_file": self.source_file,
            },
        )


class TypeRule(BaseModel):
    """A type system rule from the sv0 specification."""

    name: str
    description: str
    category: str
    section_number: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.TYPE_RULE,
            properties={
                "description": self.description,
                "category": self.category,
                "section_number": self.section_number,
            },
        )


class ContractRule(BaseModel):
    """A contract programming rule from the sv0 specification."""

    name: str
    description: str
    clause_type: Literal["requires", "ensures", "loop_invariant", "borrows", "no_alias"]
    scope: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.CONTRACT_RULE,
            properties={
                "description": self.description,
                "clause_type": self.clause_type,
                "scope": self.scope,
            },
        )


class MemoryRule(BaseModel):
    """A memory management rule from the sv0 specification."""

    name: str
    description: str
    category: Literal["ownership", "copy", "references", "borrow_tracking", "unsafe"]

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.MEMORY_RULE,
            properties={
                "description": self.description,
                "category": self.category,
            },
        )


class KeywordEntry(BaseModel):
    """A keyword defined in the sv0 language."""

    name: str
    purpose: str
    category: Literal[
        "binding",
        "function",
        "control_flow",
        "type_def",
        "visibility",
        "module",
        "safety",
        "casting",
        "self",
        "contract",
        "literal",
        "assertion",
    ]

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.KEYWORD,
            properties={
                "purpose": self.purpose,
                "category": self.category,
            },
        )


class OperatorEntry(BaseModel):
    """An operator defined in the sv0 language."""

    name: str
    symbol: str
    purpose: str
    arity: Literal["unary", "binary", "postfix"]
    trait_desugaring: str | None = None

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        properties = {
            "symbol": self.symbol,
            "purpose": self.purpose,
            "arity": self.arity,
        }
        if self.trait_desugaring is not None:
            properties["trait_desugaring"] = self.trait_desugaring
        return Entity(
            name=self.name,
            entity_type=EntityType.OPERATOR,
            properties=properties,
        )


class DesignDecision(BaseModel):
    """A recorded design decision for the sv0 language."""

    decision_id: str
    summary: str
    rationale: str

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.decision_id,
            entity_type=EntityType.DESIGN_DECISION,
            properties={
                "summary": self.summary,
                "rationale": self.rationale,
            },
        )


class PrimitiveTypeEntry(BaseModel):
    """A primitive type defined in the sv0 language."""

    name: str
    width: int
    signed: bool | None = None
    copy: bool

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        properties: dict[str, int | bool] = {
            "width": self.width,
            "copy": self.copy,
        }
        if self.signed is not None:
            properties["signed"] = self.signed
        return Entity(
            name=self.name,
            entity_type=EntityType.PRIMITIVE_TYPE,
            properties=properties,
        )


class TraitSpecEntry(BaseModel):
    """A trait specification from the sv0 language."""

    name: str
    description: str
    methods: list[str] = Field(default_factory=list)

    def to_entity(self) -> Entity:
        """Convert to a graph entity node."""
        return Entity(
            name=self.name,
            entity_type=EntityType.TRAIT_SPEC,
            properties={
                "description": self.description,
                "methods": self.methods,
            },
        )
