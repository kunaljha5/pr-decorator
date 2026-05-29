"""Shared data types passed between agent loop phases.

These dataclasses are the contracts between observe -> plan -> execute -> validate.
Keeping them in one place means each phase imports from here rather than from
each other, avoiding circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ChangeCategory(str, Enum):
    """Maps a parsed change to its destination MR template section.

    Classification rules (from the spec):
      - new files            -> FEATURES_ADDED
      - modified logic       -> CODE_CHANGES or BUG_FIXES
      - docs / formatting    -> DOCS_LINTING
      - config/dependency    -> CHORES

    These values MUST match the section keys in `prompts/mr_template.txt`.
    """

    CODE_CHANGES = "Code Changes"
    FEATURES_ADDED = "Features Added"
    CHORES = "Chores"
    DOCS_LINTING = "Docs & Linting"
    BUG_FIXES = "Bug Fixes"


# The fixed set of sections every MR report must contain, in output order.
# Purpose and Ticket ID are header fields; the rest mirror the JSON section keys
# defined in `prompts/mr_template.txt` — keep these two in sync.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Purpose",
    "Ticket ID",
    "Code Changes",
    "Features Added",
    "Bug Fixes",
    "Breaking Changes",
    "Chores",
    "Docs & Linting",
    "Risks",
)

# Sections allowed to be empty (no such change in this PR). Purpose and Code
# Changes are always required; Ticket ID is warn-only. Shared by render (skip
# empty blocks) and validate (don't error on absence) so the two never drift.
OPTIONAL_SECTIONS: frozenset[str] = frozenset(
    {
        "Features Added",
        "Bug Fixes",
        "Breaking Changes",
        "Chores",
        "Docs & Linting",
        "Risks",
    }
)

# Body sections rendered as bullet lists (everything except the Purpose prose
# and the Ticket ID identifier). This is the single source of truth shared by
# render (which sections to bulletize) and validate (which sections the
# "no file names" rule applies to) so the two phases can't disagree.
LIST_SECTIONS: frozenset[str] = frozenset(
    {
        "Code Changes",
        "Features Added",
        "Bug Fixes",
        "Breaking Changes",
        "Chores",
        "Docs & Linting",
        "Risks",
    }
)

# The one list section where naming the affected document or tool is the whole
# point, so it is exempt from the "no file names" guardrail in validate.
FILENAME_ALLOWED_SECTIONS: frozenset[str] = frozenset({"Docs & Linting"})


@dataclass
class FileChange:
    """A single file's change extracted from the diff during OBSERVE."""

    path: str
    is_new: bool = False
    is_deleted: bool = False
    added_lines: int = 0
    removed_lines: int = 0
    patch: str = ""


@dataclass
class Observation:
    """Output of the OBSERVE phase — everything collected about the PR."""

    diff: str
    files: list[FileChange] = field(default_factory=list)
    branch: str | None = None
    commit_messages: list[str] = field(default_factory=list)
    ticket_id: str | None = None
    # Enrichment mode: an existing MR title/description to build on.
    existing_title: str | None = None
    existing_description: str | None = None


@dataclass
class Plan:
    """Output of the PLAN phase — which sections to fill and why.

    `sections` maps an MR section name to the change paths/notes feeding it.
    `purpose_hint` is inferred from commits/branch to seed the Purpose section.
    """

    ticket_id: str | None = None
    purpose_hint: str | None = None
    sections: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class MRReport:
    """Output of the EXECUTE phase — the generated, structured MR."""

    title: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    # Overall review/testing risk the model assigned: "HIGH" | "Medium" | "LOW"
    # (empty if the model didn't return one — render derives a fallback).
    risk_level: str = ""


@dataclass
class ValidationResult:
    """Output of the validate (second OBSERVE) phase."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Sections that failed and should be re-planned/re-executed in isolation.
    failed_sections: list[str] = field(default_factory=list)
    # Per-section reason a section needs regenerating (e.g. a file-name leak),
    # fed back into the EXECUTE prompt so a temp=0 retry can actually converge
    # instead of reproducing the same output. Empty for plain "section is empty".
    section_feedback: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentTrace:
    """Accumulated record of each phase, saved alongside output for debugging."""

    entries: list[dict] = field(default_factory=list)

    def record(self, phase: str, **details) -> None:
        self.entries.append({"phase": phase, **details})
