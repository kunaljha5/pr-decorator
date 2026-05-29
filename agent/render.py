"""FINISH phase helpers — render an MRReport to Markdown or a JSON payload.

The Markdown form is meant to paste directly into a GitHub/GitLab MR body;
the JSON form is for programmatic API submission.
"""

from __future__ import annotations

import json
import re
import textwrap

from .models import OPTIONAL_SECTIONS, REQUIRED_SECTIONS, MRReport

# Normalize whatever casing the model returns into the canonical display label.
_RISK_LABELS = {"high": "HIGH", "medium": "Medium", "low": "LOW"}

# Body sections rendered as bullet lists (Purpose/Ticket ID stay as prose).
_LIST_SECTIONS = frozenset(
    {"Code Changes", "Features Added", "Bug Fixes", "Breaking Changes", "Chores", "Risks"}
)
# Each rendered bullet line (including the "- " marker) is wrapped to this width.
_BULLET_WIDTH = 80
# Leading bullet markers the model might emit, stripped before re-formatting.
_LEADING_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _as_bullets(text: str) -> list[str]:
    """Split a section's text into discrete bullet points.

    Handles whatever the model returns: explicit newline/`-`/`*`/`•`/numbered
    bullets, or a single paragraph (split on sentence boundaries as a fallback).
    """
    raw = text.strip()
    if not raw:
        return []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    # If the model returned one prose blob (no per-line breaks), split sentences
    # so we still produce a list rather than a single giant bullet.
    if len(lines) == 1 and not _LEADING_MARKER.match(lines[0]):
        lines = [s.strip() for s in re.split(r"(?<=[.;])\s+", lines[0]) if s.strip()]
    return [_LEADING_MARKER.sub("", line).strip() for line in lines]


def _format_bullets(text: str) -> str:
    """Render section text as a Markdown bullet list, each line ≤ 80 chars.

    Long points wrap onto continuation lines indented under the bullet text so
    no single line exceeds the width limit.
    """
    bullets = _as_bullets(text)
    if not bullets:
        return "_(none)_"
    return "\n".join(
        textwrap.fill(
            point,
            width=_BULLET_WIDTH,
            initial_indent="- ",
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        )
        for point in bullets
    )


def _risk_level(report: MRReport) -> str:
    """Return the MR's risk level, falling back to a heuristic if the model
    didn't supply a valid one (e.g. offline/stub executors)."""
    raw = (report.risk_level or "").strip().lower()
    if raw in _RISK_LABELS:
        return _RISK_LABELS[raw]
    if report.sections.get("Breaking Changes", "").strip():
        return "HIGH"
    if report.sections.get("Bug Fixes", "").strip() or report.sections.get("Risks", "").strip():
        return "Medium"
    return "LOW"


def _summary_table(report: MRReport) -> list[str]:
    """A compact single-row summary: which change types apply, plus risk level.

    Change types are derived from which sections the report actually populated,
    so the table can never disagree with the sections rendered below it.
    """

    def mark(section: str) -> str:
        return "✅" if report.sections.get(section, "").strip() else "—"

    return [
        "| Feature | Bug Fix | Chore | Breaking | Risk |",
        "|---------|---------|-------|----------|------|",
        f"| {mark('Features Added')} | {mark('Bug Fixes')} | {mark('Chores')} | "
        f"{mark('Breaking Changes')} | {_risk_level(report)} |",
    ]


def to_markdown(report: MRReport) -> str:
    """Render the report as an MR-body Markdown string following the template.

    Emits a compact summary table right after Purpose and Ticket ID, then each
    section. Empty optional sections are skipped. Every block is followed by a
    `---` rule (mirrors the dividers in `prompts/mr_template.txt`).
    """
    lines = [f"# {report.title}".rstrip(), ""]
    for section in REQUIRED_SECTIONS:
        value = report.sections.get(section, "").strip()
        if not value and section in OPTIONAL_SECTIONS:
            continue
        lines.append(f"**{section}**")
        if section in _LIST_SECTIONS:
            lines.append(_format_bullets(value))
        else:
            lines.append(value or "_(none)_")
        lines.append("")
        lines.append("---")
        lines.append("")
        # The summary table sits between the header fields and the body sections.
        if section == "Ticket ID":
            lines += _summary_table(report)
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(report: MRReport) -> str:
    """Render the report as a JSON payload for API submission."""
    return json.dumps(
        {
            "title": report.title,
            "risk_level": _risk_level(report),
            "sections": report.sections,
        },
        indent=2,
        ensure_ascii=False,
    )
