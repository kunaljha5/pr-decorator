"""Entry point for the PR Decorator Agent.

Reads a git diff (from --diff-file, a git range, or stdin), runs the agent loop,
and writes the decorated MR plus its trace to the output directory.

Examples:
    python main.py --range origin/main...HEAD --branch "$(git branch --show-current)"
    git diff origin/main | python main.py --format json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agent import loop, render
from agent.execute import BedrockExecutor

_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _read_diff(args: argparse.Namespace) -> str:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.range:
        return subprocess.run(
            ["git", "diff", args.range],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("No diff provided. Use --diff-file, --range, or pipe a diff via stdin.")


def _git_commit_messages(rng: str | None) -> list[str]:
    if not rng:
        return []
    result = subprocess.run(
        ["git", "log", "--format=%s", rng],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decorate a PR/MR into a standardized report.")
    parser.add_argument("--diff-file", help="Path to a file containing a unified git diff.")
    parser.add_argument("--range", help="Git diff range, e.g. origin/main...HEAD.")
    parser.add_argument("--branch", help="Branch name (used to infer ticket id).")
    parser.add_argument("--ticket-id", help="Explicit ticket id; overrides inference.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format for the decorated MR (default: markdown).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print to stdout only; do not write files to output/.",
    )
    parser.add_argument(
        "--model",
        help="Bedrock model id (default: Nova Pro / BEDROCK_MODEL_ID env).",
    )
    parser.add_argument(
        "--region",
        help="AWS region for Bedrock (default: BEDROCK_REGION env or ap-south-1).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    diff = _read_diff(args)

    executor_kwargs = {}
    if args.region:
        executor_kwargs["region"] = args.region
    if args.model:
        executor_kwargs["model_id"] = args.model
    executor = BedrockExecutor(**executor_kwargs) if executor_kwargs else None

    result = loop.run(
        diff,
        executor=executor,
        branch=args.branch,
        commit_messages=_git_commit_messages(args.range),
        ticket_id=args.ticket_id,
    )

    rendered = (
        render.to_json(result.report)
        if args.format == "json"
        else render.to_markdown(result.report)
    )
    print(rendered)

    for warning in result.validation.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not result.validation.ok:
        for error in result.validation.errors:
            print(f"error: {error}", file=sys.stderr)

    if not args.no_write:
        _OUTPUT_DIR.mkdir(exist_ok=True)
        ext = "json" if args.format == "json" else "md"
        (_OUTPUT_DIR / f"mr_report.{ext}").write_text(rendered, encoding="utf-8")
        (_OUTPUT_DIR / "agent_trace.json").write_text(
            json.dumps(result.trace.entries, indent=2), encoding="utf-8"
        )

    return 0 if result.validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
