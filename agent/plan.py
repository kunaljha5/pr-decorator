"""PLAN phase — change classification & section planning.

Turns an `Observation` into a `Plan`: which MR sections need filling, what
changes feed each, and a purpose hint inferred from commits/branch. The actual
prose is generated later in EXECUTE; this phase only decides *what* to write.
"""

from __future__ import annotations

from .models import ChangeCategory, FileChange, Observation, Plan

# Extensions/paths whose changes are treated as config/dependency edits.
_CONFIG_HINTS = (
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "go.mod",
    "Dockerfile",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
)

# Extensions/paths treated as documentation (routed to Docs & Linting).
_DOC_HINTS = (
    ".md",
    ".rst",
    ".adoc",
    "docs/",
    "README",
    "CHANGELOG",
    "LICENSE",
)


def _is_doc(change: FileChange) -> bool:
    return any(hint in change.path for hint in _DOC_HINTS)


def _looks_like_bugfix(observation: Observation) -> bool:
    """Heuristic: do the commit messages/branch signal a bug fix?"""
    haystack = " ".join(observation.commit_messages + [observation.branch or ""]).lower()
    return any(kw in haystack for kw in ("fix", "bug", "patch", "hotfix"))


def _is_formatting_only(change: FileChange) -> bool:
    """A formatting-only change touches lines but adds/removes roughly evenly
    with no net new logic. Heuristic placeholder until EXECUTE can inspect content."""
    if change.is_new or change.is_deleted:
        return False
    total = change.added_lines + change.removed_lines
    return total > 0 and abs(change.added_lines - change.removed_lines) <= 1


def classify(change: FileChange, observation: Observation) -> ChangeCategory:
    """Map a single file change to its MR template section."""
    if _is_doc(change):
        return ChangeCategory.DOCS_LINTING
    if any(hint in change.path for hint in _CONFIG_HINTS):
        return ChangeCategory.CHORES
    if change.is_new:
        return ChangeCategory.FEATURES_ADDED
    if _is_formatting_only(change):
        return ChangeCategory.DOCS_LINTING
    if _looks_like_bugfix(observation):
        return ChangeCategory.BUG_FIXES
    return ChangeCategory.CODE_CHANGES


def plan(observation: Observation) -> Plan:
    """Produce a `Plan` describing which sections to fill and from what changes."""
    sections: dict[str, list[str]] = {}
    for change in observation.files:
        if change.is_deleted:
            note = f"{change.path} (removed)"
            sections.setdefault(ChangeCategory.CODE_CHANGES.value, []).append(note)
            continue
        category = classify(change, observation)
        sections.setdefault(category.value, []).append(change.path)

    purpose_hint = observation.commit_messages[0] if observation.commit_messages else None

    return Plan(
        ticket_id=observation.ticket_id,
        purpose_hint=purpose_hint,
        sections=sections,
    )
