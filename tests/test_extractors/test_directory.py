"""Tests for the directory-structure extractor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sv0_mcp.extractors.directory import DirectoryExtractor
from sv0_mcp.models.base import EntityType, RelationType

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401

EXPECTED_COMPILER_PHASE_COUNT = 7
EXPECTED_PRECEDES_COUNT = 6
EXPECTED_VM_PRECEDES_COUNT = 2


class TestDirectoryExtractor:
    """Tests for DirectoryExtractor against the real toolchain workspace."""

    def test_subproject_entities(self, toolchain_root: Path) -> None:
        """Subproject entities should be created for sv0doc, sv0c, and sv0vm."""
        extractor = DirectoryExtractor(toolchain_root)
        result = extractor.extract()

        subproject_entities = [
            e for e in result.entities if e.entity_type == EntityType.SUBPROJECT
        ]
        subproject_names = {e.name for e in subproject_entities}

        expected = {"sv0doc", "sv0c", "sv0vm"}
        assert expected == subproject_names, (
            f"Expected subprojects {expected}, got {subproject_names}"
        )

    def test_compiler_pipeline(self, toolchain_root: Path) -> None:
        """Seven compiler phases with PRECEDES relationships should be created."""
        extractor = DirectoryExtractor(toolchain_root)
        result = extractor.extract()

        phase_entities = [
            e for e in result.entities if e.entity_type == EntityType.COMPILER_PHASE
        ]
        assert len(phase_entities) == EXPECTED_COMPILER_PHASE_COUNT, (
            f"Expected {EXPECTED_COMPILER_PHASE_COUNT} compiler phases, "
            f"got {len(phase_entities)}"
        )

        expected_phases = {
            "lexer",
            "parser",
            "name_resolution",
            "type_checker",
            "contract_analyzer",
            "ir",
            "c_backend",
        }
        actual_phases = {e.name for e in phase_entities}
        assert expected_phases == actual_phases, (
            f"Expected phases {expected_phases}, got {actual_phases}"
        )

        precedes_rels = [
            r
            for r in result.relationships
            if r.relation_type == RelationType.PRECEDES
            and r.source in expected_phases
            and r.target in expected_phases
        ]
        assert len(precedes_rels) == EXPECTED_PRECEDES_COUNT, (
            f"Expected {EXPECTED_PRECEDES_COUNT} PRECEDES relationships "
            f"between phases, got {len(precedes_rels)}"
        )

    def test_vm_components(self, toolchain_root: Path) -> None:
        """Bytecode, interpreter, and runtime VM components should be created."""
        extractor = DirectoryExtractor(toolchain_root)
        result = extractor.extract()

        vm_entities = [
            e for e in result.entities if e.entity_type == EntityType.VM_COMPONENT
        ]
        vm_names = {e.name for e in vm_entities}

        expected = {"bytecode", "interpreter", "runtime"}
        assert expected == vm_names, f"Expected VM components {expected}, got {vm_names}"

        vm_precedes = [
            r
            for r in result.relationships
            if r.relation_type == RelationType.PRECEDES
            and r.source in expected
            and r.target in expected
        ]
        assert len(vm_precedes) == EXPECTED_VM_PRECEDES_COUNT, (
            f"Expected {EXPECTED_VM_PRECEDES_COUNT} PRECEDES relationships "
            f"between VM components, got {len(vm_precedes)}"
        )
