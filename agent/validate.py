"""OBSERVE (post-execute) phase — output validation.

Checks the generated `MRReport` against the spec's hard contracts:
  - all required sections populated (no empty),
  - ticket id present (warn-only if missing),
  - title in imperative mood.
Sections that fail are surfaced so the loop can re-plan/re-execute *only* them.
"""

from __future__ import annotations

from .models import REQUIRED_SECTIONS, MRReport, ValidationResult

# A small allow-list of imperative-mood opening verbs for MR titles.
_IMPERATIVE_VERBS = frozenset(
    {
        "add",
        "fix",
        "refactor",
        "remove",
        "update",
        "implement",
        "introduce",
        "improve",
        "rename",
        "bump",
        "drop",
        "support",
        "handle",
        "prevent",
        "migrate",
        "document",
    }
)

# Sections allowed to legitimately be empty (no such change in this PR).
_OPTIONAL_WHEN_ABSENT = frozenset({"Features Added", "Linting Fixed", "Bug Fixed"})


def _is_imperative(title: str) -> bool:
    first = title.strip().split(" ", 1)[0].lower() if title.strip() else ""
    return first in _IMPERATIVE_VERBS


def validate(report: MRReport) -> ValidationResult:
    """Validate a generated report; return errors, warnings, and failed sections."""
    errors: list[str] = []
    warnings: list[str] = []
    failed: list[str] = []

    if not report.title.strip():
        errors.append("MR Title is empty.")
        failed.append("Title")
    elif not _is_imperative(report.title):
        warnings.append(f"MR Title may not be imperative mood: {report.title!r}")

    for section in REQUIRED_SECTIONS:
        if section == "Ticket ID":
            if not report.sections.get(section, "").strip():
                warnings.append("Ticket ID is missing.")
            continue
        if section == "Title":
            continue
        value = report.sections.get(section, "").strip()
        if value:
            continue
        if section in _OPTIONAL_WHEN_ABSENT:
            continue
        errors.append(f"Required section '{section}' is empty.")
        failed.append(section)

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        failed_sections=failed,
    )
