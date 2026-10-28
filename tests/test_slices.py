"""Tests for the file-backed checklist slice index."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sv0_mcp.slices import (
    SliceIndex,
    format_detail,
    format_page,
    normalize_status,
    parse_slices,
    split_table_row,
)

if TYPE_CHECKING:
    from pathlib import Path

_CHECKLIST = """---
key: demo-checklist
---

## Track A — foundations

| ID | slice | refs | deps | status | done when |
|----|-------|------|------|--------|-----------|
| DM-001 | **Skeleton** repo | BL-1 | — | **done** — `abc123`: skeleton | tree exists |
| DM-002 | Parser for `a|b` cells | BL-2 | DM-001 | todo | `x | y` parses |
| DM-003 | Needs two | BL-3 | DM-001, DM-002 | wip | both |
| DM-004 | Blocked one | BL-4 | DM-099 | blocked | later |

## Track B — no status column

| ID | Epic | Title | Acceptance |
|----|------|-------|------------|
| PC-1a | E1 | Imported struct | **DONE (2026-08-05):** fixture added |
| PC-2 | E1 | Still open | not yet |

| priority | slice | why first |
|----------|-------|-----------|
| 1 | DM-002 | mentioned only |
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    task = tmp_path / "task"
    task.mkdir(exist_ok=True)
    path = task / name
    path.write_text(text, encoding="utf-8")
    return path


class TestSplitTableRow:
    """Cell splitting that respects code spans."""

    def test_pipes_in_code_spans_do_not_split(self) -> None:
        """Pipes inside backticks stay in their cell."""
        assert split_table_row("| a | `x | y` | c |") == ["a", "`x | y`", "c"]

    def test_escaped_pipe(self) -> None:
        r"""``\\|`` is a literal pipe."""
        assert split_table_row(r"| a \| b | c |") == ["a | b", "c"]

    def test_non_table_line(self) -> None:
        """Lines that are not pipe rows return None."""
        assert split_table_row("plain text") is None


class TestNormalizeStatus:
    """Free-form status cells map to canonical words."""

    def test_variants(self) -> None:
        """Bold, dated, and synonym forms all normalise."""
        assert normalize_status("**done** — 2026-09-27: D-1") == "done"
        assert normalize_status("DONE (C)") == "done"
        assert normalize_status("complete") == "done"
        assert normalize_status("partial") == "wip"
        assert normalize_status("`blocked`") == "blocked"
        assert normalize_status("see notes") == "unknown"


class TestParseSlices:
    """Row extraction from checklist markdown."""

    def test_rows_status_deps_and_location(self) -> None:
        """Id rows carry status, deps, section, and 1-based line."""
        rows = {s.id: s for s in parse_slices(_CHECKLIST, "task/demo-checklist.Rmd")}
        assert set(rows) == {"DM-001", "DM-002", "DM-003", "DM-004", "PC-1a", "PC-2"}
        assert rows["DM-001"].status == "done"
        assert rows["DM-001"].title == "Skeleton repo"
        assert rows["DM-002"].deps == ["DM-001"]
        assert rows["DM-002"].cells["done when"] == "`x | y` parses"
        assert rows["DM-003"].deps == ["DM-001", "DM-002"]
        assert rows["DM-001"].section == "Track A — foundations"
        assert _CHECKLIST.splitlines()[rows["DM-002"].line - 1].startswith("| DM-002")

    def test_status_from_leading_word_without_status_column(self) -> None:
        """Tables without a status column infer it from a leading status word."""
        rows = {s.id: s for s in parse_slices(_CHECKLIST, "task/x.Rmd")}
        assert rows["PC-1a"].status == "done"
        assert rows["PC-1a"].title == "Imported struct"
        assert rows["PC-2"].status == "unknown"


class TestSliceIndex:
    """Filtering, readiness, and caching over a task directory."""

    def test_select_and_ready(self, tmp_path: Path) -> None:
        """Open filter, prefix filter, and dependency-aware readiness."""
        _write(tmp_path, "demo-checklist.Rmd", _CHECKLIST)
        index = SliceIndex(tmp_path)
        assert [s.id for s in index.select(status="open")] == ["DM-002", "DM-003", "DM-004"]
        assert [s.id for s in index.select("PC")] == ["PC-1a", "PC-2"]
        assert [s.id for s in index.select(query="struct")] == ["PC-1a"]
        # DM-003 waits on todo DM-002; DM-004 is blocked, not ready.
        assert [s.id for s in index.ready("demo")] == ["DM-002"]

    def test_checklist_row_wins_over_mentions(self, tmp_path: Path) -> None:
        """A status-bearing checklist row is canonical over a hub mention."""
        _write(tmp_path, "demo-checklist.Rmd", _CHECKLIST)
        _write(
            tmp_path,
            "demo-hub.Rmd",
            "| ID | gap |\n|----|-----|\n| DM-002 | hub mention |\n",
        )
        rows = SliceIndex(tmp_path).get("dm-002")
        assert rows[0].file == "task/demo-checklist.Rmd"
        assert rows[1].file == "task/demo-hub.Rmd"
        assert "also mentioned: task/demo-hub.Rmd" in format_detail(rows, 4000)

    def test_reparses_changed_file(self, tmp_path: Path) -> None:
        """Edits are picked up via the mtime/size cache key."""
        path = _write(tmp_path, "demo-checklist.Rmd", _CHECKLIST)
        index = SliceIndex(tmp_path)
        assert index.get("DM-002")[0].status == "todo"
        path.write_text(
            _CHECKLIST.replace("| BL-2 | DM-001 | todo |", "| BL-2 | DM-001 | done |"),
            encoding="utf-8",
        )
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        assert index.get("DM-002")[0].status == "done"


class TestFormatting:
    """Compact output stays compact."""

    def test_page_has_counts_and_continuation(self, tmp_path: Path) -> None:
        """Header tallies, one line per slice, and an offset hint."""
        _write(tmp_path, "demo-checklist.Rmd", _CHECKLIST)
        out = format_page(SliceIndex(tmp_path).select(status="any"), 2, 0, "all")
        lines = out.splitlines()
        assert lines[0].startswith("6 slices (all):")
        assert lines[1].startswith("DM-001 done")
        assert "@task/demo-checklist.Rmd:" in lines[1]
        assert "… 4 more (offset=2)." in out

    def test_detail_truncates(self, tmp_path: Path) -> None:
        """max_chars caps the cell text returned."""
        _write(tmp_path, "demo-checklist.Rmd", _CHECKLIST)
        out = format_detail(SliceIndex(tmp_path).get("DM-001"), 5)
        assert "truncated" in out


class TestRealChecklists:
    """Smoke over the meta-repo's task files when present."""

    def test_indexes_known_checklists(self, toolchain_root: Path) -> None:
        """Every big checklist yields slices with mostly known statuses."""
        index = SliceIndex(toolchain_root)
        summary = {stem: counts for stem, _path, counts in index.summary()}
        if "sv0cov-checklist" not in summary:
            return
        counts = summary["sv0cov-checklist"]
        assert sum(counts.values()) > 100  # noqa: PLR2004
        assert counts["unknown"] == 0
