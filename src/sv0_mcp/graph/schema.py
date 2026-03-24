"""Schema and constraint management for the sv0 knowledge graph."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sv0_mcp.models.base import EntityType

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


def _clean_stale_labels(client: GraphClient) -> int:
    """Remove entity-type labels that no longer match the ``entity_type`` property.

    Returns the number of nodes that were cleaned.
    """
    all_labels = [et.value for et in EntityType]
    cleaned = 0
    for label in all_labels:
        results = client.execute_write(
            f"MATCH (n:{label}) "
            "WHERE n.entity_type <> $label "
            f"REMOVE n:{label} "
            "RETURN count(n) AS cnt",
            {"label": label},
        )
        cnt = results[0]["cnt"] if results else 0
        if cnt:
            logger.info("Removed stale label %s from %d nodes", label, cnt)
            cleaned += cnt
    return cleaned


def apply_schema(client: GraphClient) -> None:
    """Apply all constraints, indexes, and label cleanup to the graph.

    Creates the required uniqueness constraints and text
    indexes if they do not already exist, then removes any
    stale entity-type labels left by previous sync operations.

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
    cleaned = _clean_stale_labels(client)
    logger.info(
        "Schema applied: %d constraints, %d indexes, %d stale labels cleaned",
        len(CONSTRAINTS),
        len(INDEXES),
        cleaned,
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
