"""Schema and constraint management for the sv0 knowledge graph."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sv0_mcp.graph.client import GraphClient

logger = logging.getLogger(__name__)

CONSTRAINTS: list[str] = [
    (
        "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS "
        "FOR (e:Entity) REQUIRE e.name IS UNIQUE"
    ),
]

INDEXES: list[str] = [
    (
        "CREATE INDEX entity_type_index IF NOT EXISTS "
        "FOR (e:Entity) ON (e.entity_type)"
    ),
    (
        "CREATE TEXT INDEX entity_name_text IF NOT EXISTS "
        "FOR (e:Entity) ON (e.name)"
    ),
    (
        "CREATE TEXT INDEX entity_observations_text "
        "IF NOT EXISTS FOR (e:Entity) ON (e.observations)"
    ),
]


def apply_schema(client: GraphClient) -> None:
    """Apply all constraints and indexes to the graph.

    Creates the required uniqueness constraints and text
    indexes if they do not already exist.

    Args:
        client: Active graph client instance.
    """
    for constraint in CONSTRAINTS:
        client.execute_write(constraint)
        logger.debug(
            "Applied constraint: %s", constraint[:60]
        )
    for index in INDEXES:
        client.execute_write(index)
        logger.debug("Applied index: %s", index[:60])
    logger.info(
        "Schema applied: %d constraints, %d indexes",
        len(CONSTRAINTS),
        len(INDEXES),
    )


def drop_schema(client: GraphClient) -> None:
    """Drop all sv0-specific constraints and indexes.

    Removes the uniqueness constraints and indexes created
    by :func:`apply_schema`.  Uses ``IF EXISTS`` so that
    calling this on a clean database is safe.

    Args:
        client: Active graph client instance.
    """
    drop_statements = [
        "DROP CONSTRAINT entity_name_unique IF EXISTS",
        "DROP INDEX entity_type_index IF EXISTS",
        "DROP INDEX entity_name_text IF EXISTS",
        "DROP INDEX entity_observations_text IF EXISTS",
    ]
    for stmt in drop_statements:
        client.execute_write(stmt)
        logger.debug("Dropped: %s", stmt)
    logger.info(
        "Schema dropped: %d statements",
        len(drop_statements),
    )
