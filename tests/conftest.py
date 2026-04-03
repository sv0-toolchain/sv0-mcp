"""Shared fixtures for the sv0-mcp test suite."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from sv0_mcp.config import Sv0McpSettings

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture  # noqa: F401
    from _pytest.fixtures import FixtureRequest  # noqa: F401
    from _pytest.logging import LogCaptureFixture  # noqa: F401
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401
    from pytest_mock.plugin import MockerFixture  # noqa: F401


@pytest.fixture
def toolchain_root() -> Path:
    """Return the absolute path to the sv0-toolchain workspace root.

    Uses ``SV0TOOLCHAIN_ROOT`` when set (standalone CI checks out the meta-repo
    beside this package). When ``sv0-mcp`` lives under the meta-repo, the parent
    of the ``sv0-mcp`` directory is the toolchain root.
    """
    from pathlib import Path as _Path  # noqa: PLC0415

    env = os.environ.get("SV0TOOLCHAIN_ROOT", "").strip()
    if env:
        return _Path(env).expanduser().resolve()
    here = _Path(__file__).resolve()
    mcp_root = here.parent.parent
    parent = mcp_root.parent
    if (parent / "sv0doc").is_dir() and (parent / "sv0c").is_dir():
        return parent
    return mcp_root


@pytest.fixture
def sample_ebnf() -> str:
    """Return a minimal EBNF grammar string for testing."""
    return (
        "(* 1. Expressions *)\n"
        "expr = term , { '+' , term } ;\n"
        "term = factor , { '*' , factor } ;\n"
        "factor = ident | '(' , expr , ')' ;\n"
        "ident = letter , { letter | digit } ;\n"
        "\n"
        "(* D1: Expression precedence follows standard mathematical convention *)\n"
        "(* Multiplication binds tighter than addition. *)\n"
    )


@pytest.fixture
def sample_rmd() -> str:
    """Return a sample .Rmd file with YAML front matter for testing."""
    return (
        "---\n"
        "key: sv0c-lexer\n"
        "title: Implement Lexer\n"
        "state: in_progress\n"
        "type: task\n"
        "tags: [compiler, lexer]\n"
        "created: 2025-06-01\n"
        "---\n"
        "\n"
        "/require: sml-nj\n"
        "/include: sv0doc-extract-grammar.Rmd\n"
        "/env: SRC_DIR=sv0c/sml/lexer\n"
        "\n"
        "## phase 1: Token Definitions\n"
        "\n"
        "Define the token types for the sv0 language.\n"
    )


@pytest.fixture
def settings(toolchain_root: Path) -> Sv0McpSettings:
    """Create Sv0McpSettings pointing to the real toolchain root."""
    return Sv0McpSettings(toolchain_root=toolchain_root)
