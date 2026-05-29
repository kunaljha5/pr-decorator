"""OBSERVE (post-execute) phase — output validation.

Checks the generated `MRReport` against the spec's hard contracts:
  - all required sections populated (no empty),
  - ticket id present (warn-only if missing),
  - title in imperative mood,
  - list sections don't leak file names/paths (warn-only). Docs & Linting may
    name a document or tool but still may not cite raw source/test file paths.
Sections that fail are surfaced so the loop can re-plan/re-execute *only* them.
"""

from __future__ import annotations

import re

from .models import (
    FILENAME_ALLOWED_SECTIONS,
    LIST_SECTIONS,
    OPTIONAL_SECTIONS,
    REQUIRED_SECTIONS,
    MRReport,
    ValidationResult,
)

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


def _is_imperative(title: str) -> bool:
    first = title.strip().split(" ", 1)[0].lower() if title.strip() else ""
    return first in _IMPERATIVE_VERBS


# File extensions split by kind. Doc files MAY be named in Docs & Linting (that
# is the point of the section); source/config files never may, in any section.
# Kept narrow so ordinary prose (decimals, version strings, "e.g.") isn't flagged.
_DOC_EXTENSIONS = ("md", "rst", "adoc", "txt")
_CODE_EXTENSIONS = (
    "py",
    "pyi",
    "js",
    "jsx",
    "ts",
    "tsx",
    "json",
    "yaml",
    "yml",
    "toml",
    "cfg",
    "ini",
    "lock",
    "sh",
    "go",
    "rs",
    "java",
    "rb",
    "c",
    "cpp",
    "h",
    "hpp",
    "css",
    "html",
)


def _ext_group(extensions: tuple[str, ...]) -> str:
    return r"\b[\w-]+\.(?:" + "|".join(extensions) + r")\b"


# Source/config file paths (e.g. `loop.py`, `test_render.py`, `pyproject.toml`):
# never appropriate as raw names, including in Docs & Linting — there, only the
# affected document or tool may be named, and a test/source file is neither.
_CODE_FILENAME_RE = re.compile(_ext_group(_CODE_EXTENSIONS))
# Any file name/path — adds doc files and bare conventional names. Used for the
# sections that must describe the change conceptually. Bare names are
# case-sensitive to avoid flagging the common-word form ("read me", "license").
_ANY_FILENAME_RE = re.compile(
    _ext_group(_DOC_EXTENSIONS + _CODE_EXTENSIONS)
    + r"|\b(?:README|CHANGELOG|LICENSE|Dockerfile|Makefile)\b"
)


def _leaks(text: str, pattern: re.Pattern[str]) -> list[str]:
    """Return distinct file-name/path tokens matched by `pattern`, in order."""
    seen: dict[str, None] = {}
    for match in pattern.finditer(text):
        seen.setdefault(match.group(0), None)
    return list(seen)


def validate(report: MRReport) -> ValidationResult:
    """Validate a generated report; return errors, warnings, and failed sections."""
    errors: list[str] = []
    warnings: list[str] = []
    failed: list[str] = []
    section_feedback: dict[str, str] = {}

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
        if section in OPTIONAL_SECTIONS:
            continue
        errors.append(f"Required section '{section}' is empty.")
        failed.append(section)

    # No-file-names guardrail: list sections must describe the change
    # conceptually. Docs & Linting may name the affected document or tool, but
    # still may NOT cite raw source/test file paths (those changes belong in
    # Chores/Code Changes). A leak does NOT fail the run (stays a warning, so the
    # exit code still means "a required section is empty"), but it does mark the
    # section for re-execution with corrective feedback so a retry can fix it.
    for section in LIST_SECTIONS:
        text = report.sections.get(section, "")
        if section in FILENAME_ALLOWED_SECTIONS:
            leaks = _leaks(text, _CODE_FILENAME_RE)
            reason = (
                f"references source/test file paths ({', '.join(leaks)}); name "
                f"the document or tool instead, and move test/source changes to "
                f"Chores or Code Changes"
            )
        else:
            leaks = _leaks(text, _ANY_FILENAME_RE)
            reason = (
                f"references file names/paths ({', '.join(leaks)}); describe the "
                f"change conceptually instead"
            )
        if leaks:
            warnings.append(f"Section '{section}' {reason}.")
            if section not in failed:
                failed.append(section)
            section_feedback[section] = f"the previous attempt {reason}"

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        failed_sections=failed,
        section_feedback=section_feedback,
    )
