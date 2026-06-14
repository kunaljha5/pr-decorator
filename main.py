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

from agent import config, loop, render
from agent.execute import BedrockExecutor, MissingCredentialsError

_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _run_git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    """Run a git command, capturing output decoded as UTF-8.

    Git emits UTF-8, but `text=True` alone decodes with the platform locale
    (cp1252 on Windows), which raises UnicodeDecodeError on the subprocess reader
    thread for any non-Latin-1 byte — there it returns stdout=None and the caller
    then trips on `None.strip()`. Forcing UTF-8 with `errors="replace"` makes the
    CLI behave the same on Windows/Git Bash as on macOS/Linux.
    """
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def _git_diff(rng: str, context_lines: int) -> str:
    return _run_git(["diff", f"--unified={context_lines}", rng], check=True).stdout


def _current_branch() -> str | None:
    return _run_git(["branch", "--show-current"]).stdout.strip() or None


def _detect_base() -> str | None:
    """Pick a base ref to diff the current branch against, preferring remotes."""
    for ref in ("origin/main", "origin/master", "origin/develop", "main", "master", "develop"):
        if _run_git(["rev-parse", "--verify", "--quiet", ref]).returncode == 0:
            return ref
    return None


def _read_diff(args: argparse.Namespace) -> str:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.range:
        return _git_diff(args.range, args.context_lines)
    if not sys.stdin.isatty():
        # Read raw bytes and decode UTF-8 so a piped diff with non-Latin-1 bytes
        # doesn't crash on the Windows locale codec (same reason as _run_git).
        return sys.stdin.buffer.read().decode("utf-8", errors="replace")

    # Zero-arg default: decorate the current branch against its base branch.
    base = _detect_base()
    if not base:
        raise SystemExit(
            "No diff provided and no base branch found (origin/main, main, ...). "
            "Use --diff-file, --range, or pipe a diff via stdin."
        )
    args.range = f"{base}...HEAD"
    diff = _git_diff(args.range, args.context_lines)
    if not diff.strip():
        raise SystemExit(f"No changes between {base} and HEAD — nothing to decorate.")
    print(f"(auto) decorating current branch vs {base} ({args.range})", file=sys.stderr)
    return diff


def _git_commit_messages(rng: str | None) -> list[str]:
    if not rng:
        return []
    result = _run_git(["log", "--format=%s", rng])
    return [line for line in result.stdout.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decorate a PR/MR into a standardized report.")
    parser.add_argument("--diff-file", help="Path to a file containing a unified git diff.")
    parser.add_argument("--range", help="Git diff range, e.g. origin/main...HEAD.")
    parser.add_argument("--branch", help="Branch name (used to infer ticket id).")
    parser.add_argument("--ticket-id", help="Explicit ticket id; overrides inference.")
    parser.add_argument(
        "--config",
        help="Path to a .pr-decorator.yml config (default: auto-discover from cwd upward).",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default=None,
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
    parser.add_argument(
        "--context-lines",
        type=int,
        default=None,
        help="Context lines for `git diff --unified` on --range; the large "
        "default includes whole-file content for modified files (default: 100000).",
    )
    return parser


# Built-in defaults applied when neither a CLI flag nor the config file sets a value.
_DEFAULT_FORMAT = "markdown"
_DEFAULT_CONTEXT_LINES = 100000


def _resolve_settings(args: argparse.Namespace, cfg: config.Config) -> dict:
    """Resolve effective settings with precedence: CLI flag > config file > default.

    `model`/`region`/`max_*_chars` stay None when unset so `BedrockExecutor`
    applies its own env-or-builtin default (keeping env *below* the config file).
    `format`/`context_lines` get a concrete built-in default here because the CLI
    no longer defaults them (None now means "unset", not "markdown"/100000).
    """
    return {
        "model": args.model or cfg.model,
        "region": args.region or cfg.region,
        "ticket_id": args.ticket_id or cfg.ticket_id,
        "format": args.format or cfg.format or _DEFAULT_FORMAT,
        "context_lines": (
            args.context_lines
            if args.context_lines is not None
            else cfg.context_lines
            if cfg.context_lines is not None
            else _DEFAULT_CONTEXT_LINES
        ),
        "max_file_chars": cfg.max_file_chars,
        "max_total_chars": cfg.max_total_chars,
    }


def _force_utf8_console() -> None:
    """Print the report (which includes ✅/— in the summary table) as UTF-8.

    On a legacy Windows console code page, printing those characters would raise
    UnicodeEncodeError; `reconfigure` is a no-op where stdout is already UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # detached/non-reconfigurable stream
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    args = build_parser().parse_args(argv)

    try:
        cfg = config.load_config(config.find_config_file(explicit=args.config))
    except config.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for warning in cfg.warnings:
        print(f"warning: {warning}", file=sys.stderr)

    settings = _resolve_settings(args, cfg)
    args.context_lines = settings["context_lines"]  # consumed by _read_diff
    diff = _read_diff(args)

    executor_kwargs = {}
    if settings["region"]:
        executor_kwargs["region"] = settings["region"]
    if settings["model"]:
        executor_kwargs["model_id"] = settings["model"]
    if settings["max_file_chars"] is not None:
        executor_kwargs["max_file_chars"] = settings["max_file_chars"]
    if settings["max_total_chars"] is not None:
        executor_kwargs["max_total_chars"] = settings["max_total_chars"]
    executor = BedrockExecutor(**executor_kwargs) if executor_kwargs else None

    try:
        result = loop.run(
            diff,
            executor=executor,
            branch=args.branch or _current_branch(),
            commit_messages=_git_commit_messages(args.range),
            ticket_id=settings["ticket_id"],
        )
    except MissingCredentialsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = (
        render.to_json(result.report)
        if settings["format"] == "json"
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
        ext = "json" if settings["format"] == "json" else "md"
        (_OUTPUT_DIR / f"mr_report.{ext}").write_text(rendered, encoding="utf-8")
        (_OUTPUT_DIR / "agent_trace.json").write_text(
            json.dumps(result.trace.entries, indent=2), encoding="utf-8"
        )

    return 0 if result.validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
