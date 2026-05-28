"""OBSERVE phase — diff parsing & input collection.

Collects the raw diff plus optional metadata (branch, commits, ticket id,
existing MR text) into an `Observation`. Diff parsing here is intentionally
lightweight: enough structure for PLAN to classify changes, not a full
unified-diff parser.
"""

from __future__ import annotations

import re

from .models import FileChange, Observation

# Matches e.g. feat/JIRA-123-add-thing, bugfix/ABC-9, PROJ-42 anywhere in text.
_TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

_DIFF_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def extract_ticket_id(*sources: str | None) -> str | None:
    """Return the first JIRA-style ticket id found across the given sources."""
    for source in sources:
        if not source:
            continue
        match = _TICKET_RE.search(source)
        if match:
            return match.group(1)
    return None


def parse_diff(diff: str) -> list[FileChange]:
    """Parse a unified git diff into per-file `FileChange` records."""
    files: list[FileChange] = []
    current: FileChange | None = None

    for line in diff.splitlines():
        header = _DIFF_FILE_HEADER.match(line)
        if header:
            if current is not None:
                files.append(current)
            current = FileChange(path=header.group(2))
            continue
        if current is None:
            continue

        if line.startswith("new file"):
            current.is_new = True
        elif line.startswith("deleted file"):
            current.is_deleted = True
        elif line.startswith("+") and not line.startswith("+++"):
            current.added_lines += 1
            current.patch += line + "\n"
        elif line.startswith("-") and not line.startswith("---"):
            current.removed_lines += 1
            current.patch += line + "\n"

    if current is not None:
        files.append(current)
    return files


def observe(
    diff: str,
    *,
    branch: str | None = None,
    commit_messages: list[str] | None = None,
    ticket_id: str | None = None,
    existing_title: str | None = None,
    existing_description: str | None = None,
) -> Observation:
    """Build an `Observation` from a diff and optional metadata."""
    commit_messages = commit_messages or []
    resolved_ticket = ticket_id or extract_ticket_id(branch, *commit_messages)

    return Observation(
        diff=diff,
        files=parse_diff(diff),
        branch=branch,
        commit_messages=commit_messages,
        ticket_id=resolved_ticket,
        existing_title=existing_title,
        existing_description=existing_description,
    )
