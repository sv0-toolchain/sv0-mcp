"""File-backed index of checklist slices in ``task/**/*.Rmd``.

Checklist files track work as markdown table rows keyed by a stable slice id
(``SS-190``, ``CV-012``, ``M3-S-004``, ``TID-001`` …).  A single row can run to
thousands of characters of prose, so reading a checklist to find the next
open slice costs tens of thousands of tokens.  This module parses those rows
into compact :class:`Slice` records so MCP tools can answer with one line per
slice and hand out the full row only on request.

The index reads files directly (no Neo4j) and re-parses a file only when its
``mtime``/size changes.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# ``SS-190``, ``M3-S-004``, ``PC-1a``, ``T0-2`` — optionally wrapped in ``**``/backticks.
_SLICE_ID_RE = re.compile(r"^[*`]*(?P<id>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[a-z]?)[*`]*$")
_DEP_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[a-z]?\b")
_HEADING_RE = re.compile(r"^#{2,4}\s+(?P<title>.+?)\s*$")
_MARKDOWN_NOISE_RE = re.compile(r"[*`]|<!--.*?-->")
_LEADING_STATUS_RE = re.compile(
    r"^\W*(?P<word>done|todo|wip|blocked|deferred|partial|draft)\b",
    re.IGNORECASE,
)

_TITLE_MAX = 90

_ID_HEADERS = frozenset({"id", "slice"})
_TITLE_HEADERS = ("slice", "title", "feature")
_STATUS_HEADERS = ("status",)
_DEPS_HEADERS = ("deps", "dependency", "dependencies")

STATUS_ALIASES: dict[str, str] = {
    "done": "done",
    "complete": "done",
    "completed": "done",
    "closed": "done",
    "shipped": "done",
    "met": "done",
    "todo": "todo",
    "open": "todo",
    "wip": "wip",
    "partial": "wip",
    "active": "wip",
    "blocked": "blocked",
    "deferred": "deferred",
    "draft": "draft",
}
OPEN_STATUSES = frozenset({"todo", "wip", "blocked"})


class Slice(BaseModel):
    """One checklist row keyed by a slice id."""

    id: str
    title: str
    status: str
    deps: list[str] = Field(default_factory=list)
    file: str
    line: int
    section: str = ""
    cells: dict[str, str] = Field(default_factory=dict)

    @property
    def checklist(self) -> str:
        """Owning file stem (e.g. ``sv0-strings-checklist``)."""
        return self.file.rsplit("/", 1)[-1].removesuffix(".Rmd")


# ======================================================================
# Parsing
# ======================================================================


def split_table_row(line: str) -> list[str] | None:
    r"""Split a ``| a | b |`` row into trimmed cells.

    Pipes inside backtick code spans or escaped as ``\|`` do not split cells.

    Returns:
        The cells, or ``None`` when *line* is not a pipe-table row.
    """
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
        return None
    cells: list[str] = []
    buf: list[str] = []
    in_code = False
    i = 1
    while i < len(s) - 1:
        ch = s[i]
        if ch == "\\" and s[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def normalize_status(raw: str) -> str:
    """Map a free-form status cell to a canonical status word.

    ``**done** — 2026-09-27: …`` → ``done``; ``DONE (C)`` → ``done``;
    unrecognised text → ``unknown``.
    """
    m = _LEADING_STATUS_RE.match(_MARKDOWN_NOISE_RE.sub("", raw))
    if m:
        return STATUS_ALIASES[m.group("word").lower()]
    word = re.split(r"[\s(—:,-]+", _MARKDOWN_NOISE_RE.sub("", raw).strip().lower(), maxsplit=1)[0]
    return STATUS_ALIASES.get(word, "unknown")


def _plain(text: str, limit: int = _TITLE_MAX) -> str:
    """Strip markdown emphasis and truncate to *limit* characters."""
    flat = " ".join(_MARKDOWN_NOISE_RE.sub("", text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _first_col(header: list[str], names: tuple[str, ...], skip: int = -1) -> int:
    for i, h in enumerate(header):
        if i != skip and h in names:
            return i
    return -1


def _is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", c) or not c for c in cells)


def parse_slices(text: str, rel_path: str) -> list[Slice]:
    """Extract every id-keyed table row from one ``.Rmd`` body.

    A table qualifies when its header's first column is ``ID`` or ``Slice``.
    Status comes from a ``status`` column, else from a leading status word in
    any cell (``**DONE (2026-08-05):** …``), else ``unknown``.

    Args:
        text: Full file text.
        rel_path: Path recorded on each slice (relative to the toolchain root).

    Returns:
        Slices in file order.
    """
    slices: list[Slice] = []
    header: list[str] | None = None
    section = ""
    for lineno, line in enumerate(text.splitlines(), start=1):
        heading = _HEADING_RE.match(line)
        if heading:
            section = _plain(heading.group("title"), 80)
            header = None
            continue
        cells = split_table_row(line)
        if cells is None:
            header = None
            continue
        low = [_MARKDOWN_NOISE_RE.sub("", c).strip().lower() for c in cells]
        if low[0] in _ID_HEADERS:
            header = low
            continue
        if header is None or _is_separator(cells):
            continue
        m = _SLICE_ID_RE.match(cells[0])
        if not m:
            continue
        slices.append(_row_to_slice(m.group("id"), header, cells, rel_path, lineno, section))
    return slices


def _row_to_slice(  # noqa: PLR0913
    slice_id: str,
    header: list[str],
    cells: list[str],
    rel_path: str,
    lineno: int,
    section: str,
) -> Slice:
    named = {
        (header[i] if i < len(header) and header[i] else f"col{i}"): c
        for i, c in enumerate(cells)
        if i > 0
    }
    title_i = _first_col(header, _TITLE_HEADERS, skip=0)
    title = cells[title_i] if 0 <= title_i < len(cells) else next(iter(named.values()), "")
    status_i = _first_col(header, _STATUS_HEADERS)
    if 0 <= status_i < len(cells):
        status = normalize_status(cells[status_i])
    else:
        status = next(
            (s for c in cells[1:] if (s := normalize_status(c)) != "unknown"),
            "unknown",
        )
    deps_i = _first_col(header, _DEPS_HEADERS)
    deps: list[str] = []
    if 0 <= deps_i < len(cells):
        deps = [d for d in dict.fromkeys(_DEP_ID_RE.findall(cells[deps_i])) if d != slice_id]
    return Slice(
        id=slice_id,
        title=_plain(title),
        status=status,
        deps=deps,
        file=rel_path,
        line=lineno,
        section=section,
        cells=named,
    )


# ======================================================================
# Index
# ======================================================================


class SliceIndex:
    """Lazily parsed, mtime-cached index over ``task/**/*.Rmd`` slice rows."""

    def __init__(self, toolchain_root: Path) -> None:
        """Create an index rooted at the sv0-toolchain checkout.

        Args:
            toolchain_root: Absolute path to the sv0-toolchain root.
        """
        self._root = toolchain_root
        self._cache: dict[Path, tuple[tuple[int, int], list[Slice]]] = {}

    def slices(self) -> list[Slice]:
        """Return every slice, re-parsing only files that changed."""
        task_dir = self._root / "task"
        if not task_dir.is_dir():
            return []
        seen: set[Path] = set()
        out: list[Slice] = []
        for path in sorted(task_dir.rglob("*.Rmd")):
            seen.add(path)
            st = path.stat()
            key = (st.st_mtime_ns, st.st_size)
            cached = self._cache.get(path)
            if cached is None or cached[0] != key:
                try:
                    parsed = parse_slices(
                        path.read_text(encoding="utf-8"),
                        str(path.relative_to(self._root)),
                    )
                except (OSError, UnicodeDecodeError):
                    logger.exception("Skipping unreadable task file %s", path)
                    parsed = []
                cached = (key, parsed)
                self._cache[path] = cached
            out.extend(cached[1])
        for stale in set(self._cache) - seen:
            del self._cache[stale]
        return out

    def by_id(self) -> dict[str, list[Slice]]:
        """Group slices by id; the first entry is the canonical definition.

        Rows from a file with a recognised status win over rows that merely
        mention the id (hub tables, priority lists).
        """
        groups: dict[str, list[Slice]] = {}
        for s in self.slices():
            groups.setdefault(s.id, []).append(s)
        for rows in groups.values():
            rows.sort(key=lambda s: (s.status == "unknown", "checklist" not in s.file))
        return groups

    def canonical(self) -> list[Slice]:
        """One slice per id, in file order."""
        firsts = {rows[0].file + f":{rows[0].line}" for rows in self.by_id().values()}
        return [s for s in self.slices() if f"{s.file}:{s.line}" in firsts]

    def get(self, slice_id: str) -> list[Slice]:
        """Return all rows for *slice_id* (canonical first); empty if unknown."""
        return self.by_id().get(slice_id.strip().upper(), [])

    def select(
        self,
        checklist: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> list[Slice]:
        """Filter canonical slices.

        Args:
            checklist: Substring of the owning file stem (``sv0cov``) or an
                exact id prefix (``CV``, ``M3-S``); case-insensitive.
            status: Canonical status, ``open`` (todo/wip/blocked), or ``any``.
            query: Case-insensitive substring of the id, title, or section.

        Returns:
            Matching slices in file order.
        """
        rows = self.canonical()
        if checklist:
            needle = checklist.strip().lower()
            rows = [
                s
                for s in rows
                if needle in s.checklist.lower() or s.id.lower().startswith(needle + "-")
            ]
        if status and status != "any":
            wanted = OPEN_STATUSES if status == "open" else {STATUS_ALIASES.get(status, status)}
            rows = [s for s in rows if s.status in wanted]
        if query:
            q = query.lower()
            rows = [
                s
                for s in rows
                if q in s.id.lower() or q in s.title.lower() or q in s.section.lower()
            ]
        return rows

    def ready(self, checklist: str | None = None) -> list[Slice]:
        """Open (todo/wip) slices whose known dependencies are all ``done``.

        Dependencies on ids absent from the index are treated as satisfied
        (they usually name external requirements, not slices).
        """
        status_of = {sid: rows[0].status for sid, rows in self.by_id().items()}
        return [
            s
            for s in self.select(checklist, None)
            if s.status in {"todo", "wip"}
            and all(status_of.get(d, "done") == "done" for d in s.deps)
        ]

    def summary(self) -> list[tuple[str, str, Counter[str]]]:
        """Per-checklist ``(stem, file, status counts)`` for files with slices."""
        per_file: dict[str, Counter[str]] = {}
        stems: dict[str, str] = {}
        for s in self.canonical():
            per_file.setdefault(s.file, Counter())[s.status] += 1
            stems[s.file] = s.checklist
        return [(stems[f], f, c) for f, c in per_file.items()]


# ======================================================================
# Compact formatting (shared by MCP tools and CLI)
# ======================================================================


def format_line(s: Slice) -> str:
    """One compact line: ``SS-012 todo  title [deps: …] @file:line``."""
    deps = f" [deps: {', '.join(s.deps)}]" if s.deps else ""
    return f"{s.id} {s.status:<8} {s.title}{deps} @{s.file}:{s.line}"


def format_page(rows: list[Slice], limit: int, offset: int, label: str) -> str:
    """Render one page of slices plus a counts header and a continuation hint."""
    total = len(rows)
    if not total:
        return f"No slices match ({label})."
    counts = Counter(s.status for s in rows)
    page = rows[offset : offset + limit]
    tally = ", ".join(f"{k} {v}" for k, v in counts.most_common())
    lines = [f"{total} slices ({label}): {tally}. Showing {offset + 1}-{offset + len(page)}."]
    lines.extend(format_line(s) for s in page)
    remaining = total - offset - len(page)
    if remaining > 0:
        lines.append(f"… {remaining} more (offset={offset + len(page)}).")
    lines.append("Full row: get_slice(id).")
    return "\n".join(lines)


def format_detail(rows: list[Slice], max_chars: int) -> str:
    """Render the canonical row in full (cells truncated at *max_chars* total)."""
    s = rows[0]
    lines = [
        f"{s.id} [{s.status}] {s.title}",
        f"  where: {s.file}:{s.line}" + (f"  (section: {s.section})" if s.section else ""),
    ]
    if s.deps:
        lines.append(f"  deps: {', '.join(s.deps)}")
    budget = max_chars
    for name, value in s.cells.items():
        if budget <= 0:
            lines.append("  … truncated; raise max_chars or Read the file at the line above.")
            break
        text = value if len(value) <= budget else value[:budget].rstrip() + "…"
        budget -= len(text)
        lines.append(f"  {name}: {text}")
    lines.extend(f"  also mentioned: {o.file}:{o.line} [{o.status}]" for o in rows[1:])
    return "\n".join(lines)
