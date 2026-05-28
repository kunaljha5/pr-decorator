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
      - modified logic       -> CODE_CHANGES or BUG_FIXED
      - formatting-only      -> LINTING_FIXED
      - config/dependency    -> CODE_CHANGES
    """

    CODE_CHANGES = "Code Changes"
    FEATURES_ADDED = "Features Added"
    LINTING_FIXED = "Linting Fixed"
    BUG_FIXED = "Bug Fixed"


# The fixed set of sections every MR report must contain, in output order.
# Purpose and Ticket ID are header fields; the rest come from ChangeCategory.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Purpose",
    "Ticket ID",
    ChangeCategory.CODE_CHANGES.value,
    ChangeCategory.FEATURES_ADDED.value,
    ChangeCategory.LINTING_FIXED.value,
    ChangeCategory.BUG_FIXED.value,
)


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


@dataclass
class ValidationResult:
    """Output of the validate (second OBSERVE) phase."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Sections that failed and should be re-planned/re-executed in isolation.
    failed_sections: list[str] = field(default_factory=list)


@dataclass
class AgentTrace:
    """Accumulated record of each phase, saved alongside output for debugging."""

    entries: list[dict] = field(default_factory=list)

    def record(self, phase: str, **details) -> None:
        self.entries.append({"phase": phase, **details})
