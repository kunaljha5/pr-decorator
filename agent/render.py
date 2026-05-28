"""FINISH phase helpers — render an MRReport to Markdown or a JSON payload.

The Markdown form is meant to paste directly into a GitHub/GitLab MR body;
the JSON form is for programmatic API submission.
"""

from __future__ import annotations

import json

from .models import REQUIRED_SECTIONS, MRReport


def to_markdown(report: MRReport) -> str:
    """Render the report as an MR-body Markdown string following the template."""
    lines = [f"# {report.title}".rstrip(), ""]
    for section in REQUIRED_SECTIONS:
        value = report.sections.get(section, "").strip()
        if not value and section in {"Features Added", "Linting Fixed", "Bug Fixed"}:
            continue
        lines.append(f"**{section}**")
        lines.append(value or "_(none)_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(report: MRReport) -> str:
    """Render the report as a JSON payload for API submission."""
    return json.dumps(
        {"title": report.title, "sections": report.sections},
        indent=2,
        ensure_ascii=False,
    )
