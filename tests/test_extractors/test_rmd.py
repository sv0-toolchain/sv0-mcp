"""Tests for the Rmd task-file extractor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sv0_mcp.extractors.rmd import RmdExtractor
from sv0_mcp.models.base import EntityType, RelationType

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401


class TestRmdExtractor:
    """Tests for RmdExtractor against real task/*.Rmd files."""

    def test_extract_tasks(self, toolchain_root: Path) -> None:
        """Task entities should be created from .Rmd files in the task directory."""
        extractor = RmdExtractor(toolchain_root)
        result = extractor.extract()

        task_entities = [e for e in result.entities if e.entity_type == EntityType.TASK]
        assert len(task_entities) > 0, "Expected at least one Task entity"

        keys = {e.name for e in task_entities}
        assert "sv0c-lexer" in keys, "Expected sv0c-lexer task"

    def test_extract_milestones(self, toolchain_root: Path) -> None:
        """Milestone entities should be created from milestone .Rmd files."""
        extractor = RmdExtractor(toolchain_root)
        result = extractor.extract()

        milestone_entities = [
            e for e in result.entities if e.entity_type == EntityType.MILESTONE
        ]
        assert len(milestone_entities) > 0, "Expected at least one Milestone entity"

        milestone_keys = {e.name for e in milestone_entities}
        expected = {"sv0c-milestone-1", "sv0doc-milestone-0", "sv0vm-milestone-2"}
        found = expected & milestone_keys
        assert len(found) > 0, (
            f"Expected milestones among {expected}, got {milestone_keys}"
        )

    def test_includes_relationships(self, toolchain_root: Path) -> None:
        """/include: directives should create INCLUDES relationships."""
        extractor = RmdExtractor(toolchain_root)
        result = extractor.extract()

        includes_rels = [
            r for r in result.relationships if r.relation_type == RelationType.INCLUDES
        ]
        assert len(includes_rels) > 0, "Expected at least one INCLUDES relationship"

    def test_depends_on_relationships(self, toolchain_root: Path) -> None:
        """/require: directives should create DEPENDS_ON relationships."""
        extractor = RmdExtractor(toolchain_root)
        result = extractor.extract()

        depends_rels = [
            r for r in result.relationships if r.relation_type == RelationType.DEPENDS_ON
        ]
        assert len(depends_rels) > 0, "Expected at least one DEPENDS_ON relationship"

    def test_missing_task_dir(self, tmp_path: Path) -> None:
        """Extractor should return empty result when task directory is absent."""
        extractor = RmdExtractor(tmp_path)
        result = extractor.extract()

        assert len(result.entities) == 0
        assert len(result.relationships) == 0
