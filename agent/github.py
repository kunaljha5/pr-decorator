"""GitHub-side helpers for the Action and the (preview) App.

The core decoration loop produces an MR body; *writing* it back to a PR is a
separate concern handled here. `merge_pr_body` folds freshly generated content
into an existing PR body (or comment) between sentinel markers so manual edits
made outside the block survive re-runs — the default "no-clobber" behavior. An
`overwrite` flag forces a full replace.

This module is the single shared implementation: `action.yml` shells out to the
`pr-decorator-merge` console script (`_cli`), and the App skeleton imports
`merge_pr_body` directly — so both update PRs identically.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_START = "<!-- pr-decorator:start -->"
DEFAULT_END = "<!-- pr-decorator:end -->"


def markers_for(namespace: str) -> tuple[str, str]:
    """Build the start/end marker pair for a namespace (e.g. 'pr-decorator')."""
    return (f"<!-- {namespace}:start -->", f"<!-- {namespace}:end -->")


def extract_block(
    body: str | None,
    start_marker: str = DEFAULT_START,
    end_marker: str = DEFAULT_END,
) -> str | None:
    """Return the content between the first valid marker pair, or None.

    "Valid" means both markers are present and `end` comes after `start`; a
    half-present or out-of-order pair is treated as absent so callers never
    slice on a bogus index.
    """
    if not body:
        return None
    start = body.find(start_marker)
    end = body.find(end_marker)
    if start == -1 or end == -1 or end < start:
        return None
    return body[start + len(start_marker) : end].strip()


def merge_pr_body(
    existing: str | None,
    generated: str,
    *,
    overwrite: bool = False,
    start_marker: str = DEFAULT_START,
    end_marker: str = DEFAULT_END,
) -> str:
    """Fold `generated` into `existing`, returning the new body.

    - overwrite=True → return just the marker block, dropping everything else.
    - empty/None existing → return just the block.
    - valid marker pair present → replace only the content between the markers,
      preserving any text before `start` and after `end`.
    - markers absent (or malformed) and not overwriting → append a fresh block
      below the existing body, leaving it untouched.

    Idempotent: re-running with the same `generated` yields a byte-identical
    body, which keeps the Action's `edited`-event guard from looping.
    """
    block = f"{start_marker}\n{generated.strip()}\n{end_marker}"

    if overwrite or not (existing and existing.strip()):
        return block

    start = existing.find(start_marker)
    end = existing.find(end_marker)
    if start != -1 and end != -1 and end > start:
        before = existing[:start]
        after = existing[end + len(end_marker) :]
        return f"{before}{block}{after}"

    return f"{existing.rstrip()}\n\n{block}\n"


def _cli(argv: list[str] | None = None) -> int:
    """`pr-decorator-merge` entry point — used by action.yml to avoid inline code.

    Reads the existing body and generated content from files, writes the merged
    body to `--out-file` (or stdout). Markers default to the `pr-decorator`
    namespace; override with `--markers`.
    """
    parser = argparse.ArgumentParser(
        prog="pr-decorator-merge",
        description="Merge a generated PR description into an existing PR body using markers.",
    )
    parser.add_argument("--existing-file", help="File with the current PR body (omit if none).")
    parser.add_argument(
        "--generated-file", required=True, help="File with the newly generated MR body."
    )
    parser.add_argument("--out-file", help="Where to write the merged body (default: stdout).")
    parser.add_argument(
        "--markers",
        default="pr-decorator",
        help="Marker namespace; produces <!-- {ns}:start/end --> (default: pr-decorator).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the whole body instead of merging within markers.",
    )
    args = parser.parse_args(argv)

    existing = None
    if args.existing_file:
        with open(args.existing_file, encoding="utf-8") as fh:
            existing = fh.read()
    with open(args.generated_file, encoding="utf-8") as fh:
        generated = fh.read()

    start_marker, end_marker = markers_for(args.markers)
    merged = merge_pr_body(
        existing,
        generated,
        overwrite=args.overwrite,
        start_marker=start_marker,
        end_marker=end_marker,
    )

    if args.out_file:
        with open(args.out_file, "w", encoding="utf-8") as fh:
            fh.write(merged)
    else:
        sys.stdout.write(merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
