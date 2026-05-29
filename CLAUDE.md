# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**PR Decorator Agent** — a Python + AWS Bedrock CLI that takes a git diff plus optional
metadata and produces a standardized Merge Request report (Markdown or JSON). It runs a
single-pass agentic loop:

```
OBSERVE → PLAN → EXECUTE → OBSERVE (validate) → FINISH
```

`README.md` is the authoritative product spec. The system is **implemented** — when changing
behavior, keep code, README, and `prompts/mr_template.txt` in sync.

## Architecture

The loop is the core. Each phase is a module under `agent/`, wired together by `agent/loop.py`
(`run()`), with `main.py` as the CLI entry point (also the `pr-decorator` console script).

- **`agent/models.py`** — the dataclass contracts passed between phases (`Observation`, `Plan`,
  `MRReport`, `ValidationResult`, `AgentTrace`, `FileChange`) and the `ChangeCategory` enum.
  **Read this first** — every phase imports types from here, never from each other, which is
  what keeps the phases decoupled and avoids circular imports. `REQUIRED_SECTIONS` defines the
  fixed output sections (Purpose, Ticket ID, Code Changes, Features Added, Bug Fixes, Breaking
  Changes, Chores, Docs & Linting, Risks) and **must stay in sync with the JSON keys in
  `prompts/mr_template.txt`**;
  `OPTIONAL_SECTIONS` is the shared set that may be empty (skipped on render, not flagged on
  validate). `MRReport.risk_level` ("HIGH"|"Medium"|"LOW") is a top-level field the model returns.
- **`agent/observe.py`** — lightweight diff parsing (not a full unified-diff parser) into
  `FileChange` records (keeps the *whole* per-file patch body, not just changed lines), plus
  ticket-id extraction via regex from branch/commits.
- **`agent/plan.py`** — heuristic classification of each `FileChange` into an MR section
  (docs/`.md` and near-symmetric add/remove → Docs & Linting; config/deps → Chores; new file →
  Features Added; fix/bug keywords in commits → Bug Fixes; else Code Changes). These are only
  *hints* fed to the LLM — the model re-judges intent from actual code content. The system prompt
  tells the model to **synthesize the story** (group dependent changes, never list file names or
  one-bullet-per-file); `execute.py` frames file contents as "evidence", not the answer's skeleton.
- **`agent/execute.py`** — `BedrockExecutor` wraps the `bedrock-runtime` client and calls the
  `converse` API. Builds the user prompt from the plan + full file content, parses the model's
  JSON response into an `MRReport`. The boto3 client is created **lazily** so the loop and tests
  run without AWS creds. System prompt is loaded from `prompts/mr_template.txt` (as packaged
  data, with a source-checkout fallback).
- **`agent/validate.py`** — the second OBSERVE: checks required sections are populated, title is
  imperative mood, ticket id present (warn-only). Returns `failed_sections` so the loop can
  re-execute **only** those.
- **`agent/render.py`** — FINISH: renders `MRReport` to Markdown (MR body) or JSON. The Markdown
  has a compact summary table right after Purpose/Ticket ID (Feature/Bug Fix/Chore/Breaking marks
  derived from which sections are populated, plus the risk level) and ends every block with `---`.
  Empty optional sections are skipped. `_risk_level()` falls back to a heuristic (Breaking → HIGH,
  Bug Fix/Risks → Medium, else LOW) when the model omits `risk_level`. Body sections in
  `_LIST_SECTIONS` (everything except Purpose/Ticket ID) render as Markdown bullet lists, each
  line hard-wrapped to ≤80 chars via `_format_bullets`/`_as_bullets` — robust to whatever bullet
  style (or prose blob) the model returns.

### Control-flow rules baked into `loop.py` (don't break these)

- **Stateless** — each `run()` is fully independent; no state carries between runs.
- **Retry**: `MAX_RETRIES = 2` on Bedrock-call exceptions. `MissingCredentialsError` is
  **non-retryable** and surfaces immediately (exit code 2 from the CLI) rather than burning retries.
- **Partial re-execution**: when validation fails, the loop re-plans/re-executes only the failed
  sections (via `generate(..., only_section=...)`), bounded by `MAX_RETRIES`.
- **Trace**: every phase appends to `AgentTrace`; written to `output/agent_trace.json` alongside
  the report. Preserve trace entries when editing phases — it's the debugging surface.
- **Output always conforms to the template** — no freeform sections.

## AWS Bedrock integration

- **Model: Amazon Nova Pro**, not Claude. Default id `apac.amazon.nova-pro-v1:0` (the APAC
  cross-region inference profile required to call Nova in `ap-south-1`). Override via
  `BEDROCK_MODEL_ID` env or `--model` (e.g. `amazon.nova-pro-v1:0` / `us.amazon.nova-pro-v1:0`).
- API: `converse` (model-agnostic). Region defaults to `ap-south-1`, override via
  `BEDROCK_REGION` / `AWS_REGION` or `--region`.
- **Auth via the standard AWS credential chain / IAM role — never hardcode keys.**
- Content size caps: `MR_MAX_FILE_CHARS` (default 12000) and `MR_MAX_TOTAL_CHARS` (default
  120000) bound prompt size; over-budget files are noted, never silently dropped.

## Development

These commands are for working **on** the package from a source checkout. End users install the
published package instead — `pip install pr-decorator` (or `uv pip install pr-decorator`) — and
run the `pr-decorator` console script; see README "Publishing to PyPI".

Python 3.12 (`.python-version`); `pyproject.toml` allows `>=3.10`. Prefer `uv`.

```bash
# Set up the dev environment (editable install with dev extras)
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"

# Run — zero-arg auto-detects base (origin/main→main→master), diffs current branch:
uv run main.py
# Explicit range / piped diff / saved file:
.venv/bin/python main.py --range origin/main...HEAD --branch "$(git branch --show-current)"
git diff origin/main | .venv/bin/python main.py --format markdown
.venv/bin/python main.py --diff-file changes.diff --ticket-id PRD-1 --format json
# Useful flags: --model --region --format{markdown,json} --no-write --context-lines N

# Lint
.venv/bin/ruff check .
.venv/bin/ruff format

# Tests (pytest, all use a fake/stub executor — no AWS or network needed)
.venv/bin/pytest
.venv/bin/pytest tests/test_loop.py::test_loop_returns_valid_report   # single test
```

> Note: the README's "Local Setup" section states a policy of no unit tests, but a working
> `tests/` suite exists and runs offline against stubbed executors. Run it.

A successful CLI run exits **0** (non-zero = a required section failed validation), prints the
decorated MR, and writes `output/mr_report.{md,json}` + `output/agent_trace.json`.

### Offline smoke test (no AWS)

Inject a stub client into `BedrockExecutor(client=...)` whose `.converse()` returns a canned JSON
payload, then call `loop.run(diff, executor=...)`. See README "Validate it worked" and the
`_FakeExecutor` pattern in `tests/test_loop.py`.

## CI / release

`.github/workflows/build.yml` builds wheel+sdist, runs `twine check`, and verifies a clean-venv
wheel install exposes the `pr-decorator` CLI and ships the packaged prompt. On `v*` tags it
publishes to PyPI via **Trusted Publishing** (OIDC, no stored tokens) and cuts a GitHub Release.
Release = bump `version` in `pyproject.toml`, then `git tag vX.Y.Z && git push origin vX.Y.Z`.