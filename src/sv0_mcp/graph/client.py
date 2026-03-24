"""Neo4j client wrapper for the sv0 knowledge graph."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import neo4j

from sv0_mcp.models.base import EntityType

if TYPE_CHECKING:
    from typing import Any

    from sv0_mcp.models.base import Entity, Relationship

logger = logging.getLogger(__name__)


class GraphClient:
    """Manages Neo4j driver lifecycle and query execution."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        """Initialize with connection parameters.

        Creates a ``neo4j.GraphDatabase.driver`` for communicating
        with the Neo4j database.

        Args:
            uri: Neo4j connection URI (e.g. ``bolt://localhost:7688``).
            user: Database username.
            password: Database password.
            database: Target database name.
        """
        self._uri = uri
        self._database = database
        self._driver = neo4j.GraphDatabase.driver(
            uri, auth=(user, password)
        )
        logger.info("GraphClient initialized for %s", uri)

    def close(self) -> None:
        """Close the underlying Neo4j driver and release resources."""
        self._driver.close()
        logger.info("GraphClient closed")

    def __enter__(self) -> GraphClient:
        """Enter the context manager, returning this client."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the context manager, closing the driver."""
        self.close()

    # ------------------------------------------------------------------
    # Generic query helpers
    # ------------------------------------------------------------------

    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read transaction and return result records.

        Args:
            query: Cypher query string.
            parameters: Optional mapping of query parameters.

        Returns:
            List of record dictionaries.
        """
        with self._driver.session(
            database=self._database,
        ) as session:
            return session.execute_read(
                lambda tx: [
                    record.data()
                    for record in tx.run(
                        query, parameters or {}
                    )
                ],
            )

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write transaction and return result records.

        Args:
            query: Cypher query string.
            parameters: Optional mapping of query parameters.

        Returns:
            List of record dictionaries.
        """
        with self._driver.session(
            database=self._database,
        ) as session:
            return session.execute_write(
                lambda tx: [
                    record.data()
                    for record in tx.run(
                        query, parameters or {}
                    )
                ],
            )

    def verify_connectivity(self) -> bool:
        """Test the connection to the Neo4j instance.

        Returns:
            ``True`` if the driver can reach the server.
        """
        try:
            self._driver.verify_connectivity()
        except neo4j.exceptions.ServiceUnavailable:
            return False
        return True

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    _ENTITY_TYPE_LABELS: tuple[str, ...] = tuple(
        et.value for et in EntityType
    )

    def merge_entity(self, entity: Entity) -> None:
        """MERGE an entity into the graph.

        Uses ``entity.name`` as the unique key.  Sets all properties
        and observations.  Applies ``entity_type`` as an additional
        Neo4j node label (e.g. ``GrammarProduction``).

        Stale type labels from previous categorisations are removed
        before the new label is applied to prevent label drift.

        Args:
            entity: The entity to merge.

        Raises:
            ValueError: If the entity-type label contains
                non-alphanumeric characters.
        """
        label = entity.entity_type.value
        if not label.isalnum():
            msg = f"Invalid entity type label: {label}"
            raise ValueError(msg)
        props = {
            k: v
            for k, v in entity.properties.items()
            if k not in ("name", "entity_type", "observations")
        }
        remove_clauses = " ".join(
            f"REMOVE n:{lbl}"
            for lbl in self._ENTITY_TYPE_LABELS
            if lbl != label
        )
        query = (
            f"MERGE (n:Entity {{name: $name}}) "
            f"{remove_clauses} "
            f"SET n:{label}, "
            "n.entity_type = $entity_type, "
            "n.observations = $observations "
            "SET n += $properties"
        )
        self.execute_write(
            query,
            {
                "name": entity.name,
                "entity_type": entity.entity_type.value,
                "observations": entity.observations,
                "properties": props,
            },
        )

    def merge_relationship(
        self, relationship: Relationship
    ) -> None:
        """MERGE a relationship between two entities.

        Source and target are matched by name.  Creates or updates
        the relationship with the given type and properties.

        Args:
            relationship: The relationship to merge.

        Raises:
            ValueError: If the relationship type contains
                invalid characters.
        """
        rel_type = relationship.relation_type.value
        if not all(c.isalnum() or c == "_" for c in rel_type):
            msg = f"Invalid relationship type: {rel_type}"
            raise ValueError(msg)
        query = (
            f"MATCH (s:Entity {{name: $source}}) "
            f"MATCH (t:Entity {{name: $target}}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r += $properties"
        )
        self.execute_write(
            query,
            {
                "source": relationship.source,
                "target": relationship.target,
                "properties": relationship.properties,
            },
        )

    def delete_entity(self, name: str) -> None:
        """Delete an entity and all its relationships by name.

        Args:
            name: Unique entity name.
        """
        self.execute_write(
            "MATCH (e:Entity {name: $name}) DETACH DELETE e",
            {"name": name},
        )

    def get_entity(
        self, name: str
    ) -> dict[str, Any] | None:
        """Get an entity by name.

        Args:
            name: Unique entity name.

        Returns:
            Properties dictionary, or ``None`` if not found.
        """
        results = self.execute_read(
            "MATCH (e:Entity {name: $name}) RETURN e",
            {"name": name},
        )
        if not results:
            return None
        return dict(results[0]["e"])

    def get_relationships(
        self,
        name: str,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get all relationships for an entity.

        Args:
            name: Entity name.
            direction: ``'outgoing'``, ``'incoming'``,
                or ``'both'``.

        Returns:
            List of relationship dictionaries.
        """
        if direction == "outgoing":
            query = (
                "MATCH (e:Entity {name: $name})"
                "-[r]->(other:Entity) "
                "RETURN type(r) AS relation_type, "
                "properties(r) AS properties, "
                "e.name AS source, other.name AS target"
            )
        elif direction == "incoming":
            query = (
                "MATCH (e:Entity {name: $name})"
                "<-[r]-(other:Entity) "
                "RETURN type(r) AS relation_type, "
                "properties(r) AS properties, "
                "other.name AS source, e.name AS target"
            )
        else:
            query = (
                "MATCH (e:Entity {name: $name})"
                "-[r]-(other:Entity) "
                "RETURN type(r) AS relation_type, "
                "properties(r) AS properties, "
                "other.name AS other_name, "
                "CASE WHEN startNode(r) = e "
                "THEN 'outgoing' ELSE 'incoming' "
                "END AS direction"
            )
        return self.execute_read(query, {"name": name})

    # ------------------------------------------------------------------
    # Search / listing
    # ------------------------------------------------------------------

    def search_entities(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across entity names and observations.

        Uses ``CONTAINS`` for simple substring matching.

        Args:
            query: Substring to search for.
            entity_type: Optional entity-type filter.
            limit: Maximum number of results.

        Returns:
            List of matching entity property dictionaries.
        """
        conditions = [
            "(e.name CONTAINS $query "
            "OR ANY(obs IN e.observations "
            "WHERE obs CONTAINS $query))",
        ]
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if entity_type:
            conditions.append(
                "e.entity_type = $entity_type"
            )
            params["entity_type"] = entity_type
        where = " AND ".join(conditions)
        cypher = (
            "MATCH (e:Entity) "
            f"WHERE {where} "
            "RETURN e "
            "LIMIT $limit"
        )
        return [
            r["e"]
            for r in self.execute_read(cypher, params)
        ]

    def get_all_entities(
        self,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all entities, optionally filtered by type.

        Args:
            entity_type: Optional entity-type filter string.

        Returns:
            List of entity property dictionaries.
        """
        if entity_type:
            cypher = (
                "MATCH (e:Entity) "
                "WHERE e.entity_type = $entity_type "
                "RETURN e"
            )
            results = self.execute_read(
                cypher, {"entity_type": entity_type}
            )
        else:
            results = self.execute_read(
                "MATCH (e:Entity) RETURN e"
            )
        return [r["e"] for r in results]
