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
  validate). `LIST_SECTIONS` (sections rendered as bullet lists) and `FILENAME_ALLOWED_SECTIONS`
  (just Docs & Linting) live here too as the **single source of truth** shared by render and
  validate, so the bulletizing and the no-file-names guardrail can't drift apart.
  `MRReport.risk_level` ("HIGH"|"Medium"|"LOW") is a top-level field the model returns.
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
  data, with a source-checkout fallback). The content caps (`max_file_chars`/`max_total_chars`)
  are **instance attributes** (default from `MR_MAX_FILE_CHARS`/`MR_MAX_TOTAL_CHARS` env, else
  built-in) so `.pr-decorator.yml` can drive them; `_render_files` takes them as args.
- **`agent/validate.py`** — the second OBSERVE: checks required sections are populated, title is
  imperative mood, ticket id present (warn-only), and that list sections don't leak file
  names/paths. A leak is a **warning, not an error** (it never flips the exit code — that still
  means "a required section is empty"), but it **does** add the section to `failed_sections` *and*
  a `section_feedback[section]` reason, so the loop re-executes it with corrective feedback. Docs &
  Linting is special-cased: it **may** name a document or tool (e.g. "the README", "ruff") but is
  still flagged for raw **source/test** paths (`.py`, `test_*.py`, etc.) — those belong in
  Chores/Code Changes. Returns `failed_sections` so the loop can re-execute **only** those.
- **`agent/render.py`** — FINISH: renders `MRReport` to Markdown (MR body) or JSON. The Markdown
  has a compact summary table right after Purpose whose **first column is the Ticket ID**, followed
  by Feature/Bug Fix/Chore/Breaking marks (derived from which sections are populated) and the risk
  level; it ends every block with `---`. Ticket ID is shown only in that table, **not** as its own
  block (missing ticket → `—`). Empty optional sections are skipped. `_risk_level()` falls back to
  a heuristic (Breaking → HIGH, Bug Fix/Risks → Medium, else LOW) when the model omits `risk_level`.
  Body sections in `LIST_SECTIONS` (everything except Purpose/Ticket ID) render as Markdown bullet
  lists, each line hard-wrapped to ≤80 chars via `_format_bullets`/`_as_bullets` — robust to whatever bullet
  style (or prose blob) the model returns.
- **`agent/config.py`** — loads an optional `.pr-decorator.yml` (auto-discovered cwd→root, or
  `--config`). `main._resolve_settings` layers it with precedence **CLI flag > config > env >
  built-in default** (CLI defaults for `--format`/`--context-lines` are now `None` so "unset" is
  distinguishable). Unknown keys / bad values are **warnings, never fatal**; a missing file is
  fine, a malformed one raises `ConfigError` (CLI exit 2). YAML parsing prefers PyYAML if present
  (optional `[yaml]` extra) but falls back to a **vendored flat-key parser** so the package stays
  boto3-only — the schema is intentionally flat.
- **`agent/github.py`** — GitHub PR-writing helpers, **shared by the Action and the App** so the
  two update PRs identically. `merge_pr_body(existing, generated, *, overwrite, start_marker,
  end_marker)` folds generated content between `<!-- pr-decorator:start/end -->` markers
  (no-clobber: text outside the block survives; `overwrite=True` replaces wholesale; idempotent).
  `_cli` backs the `pr-decorator-merge` console script that `action.yml` shells out to.

### Control-flow rules baked into `loop.py` (don't break these)

- **Stateless** — each `run()` is fully independent; no state carries between runs.
- **Retry**: `MAX_RETRIES = 4` on Bedrock-call exceptions. `MissingCredentialsError` is
  **non-retryable** and surfaces immediately (exit code 2 from the CLI) rather than burning retries.
- **Partial re-execution**: the loop re-executes only the `failed_sections` (via
  `generate(..., only_section=..., feedback=...)`), bounded by `MAX_RETRIES`. It loops **while any
  failed section remains** (not just while the report is invalid) — so file-name *leaks* (warnings)
  drive re-execution too, not only empty required sections (errors). Leak sections pass their
  `section_feedback` reason into the prompt so a `temperature=0` retry produces *different* output
  instead of reproducing the rejected section verbatim. A leak the model never fixes persists as a
  warning (exit 0); it does not fail the run.
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

## GitHub integration

Two delivery surfaces wrap the same core (`loop.run` → `render.to_markdown` →
`github.merge_pr_body`) — keep all PR-writing logic in `agent/github.py`, never duplicated.

- **`action.yml`** (repo root) — a **composite** Action so `kunaljha5/pr-decorator@v1` resolves.
  Runs via `uvx --from <pkg-or-path>` (no PATH juggling, matches the `uvx` style in `build.yml`):
  setup-uv → optional OIDC creds (`aws-actions/configure-aws-credentials@v4`, guarded on
  `aws-role-to-assume`) → compute `base...head` range from PR-coordinate inputs → run the CLI
  `--no-write` capturing stdout → merge into the PR body/comment via `pr-decorator-merge` + `gh`.
  PR coordinates (`pr-number`/`base-sha`/`head-sha`/`head-ref`) are **inputs that default to the
  `pull_request` event payload**, so the Action also works off other events (the `action-e2e.yml`
  `workflow_dispatch` run passes them explicitly). Don't subscribe to the `edited` event (loop).
- **`docs/examples/pr-decorator.yml`** — the copy-paste consumer workflow; lives under `docs/`
  (not `.github/workflows/`) so it never runs in *this* repo.
- **`app/`** — **preview skeleton only**, excluded from the wheel (not in `[tool.setuptools]
  packages`) and from the test suite. `verify_signature` (HMAC) is real; auth/HTTP are stubs that
  lazily import the `[app]` extra. Architecture in `docs/github-app.md`.

## Development

These commands are for working **on** the package from a source checkout. End users install the
published package instead — `pip install pr-decorator` (or `uv pip install pr-decorator`) — and
run the `pr-decorator` console script; see README "Publishing to PyPI".

Python 3.12 (`.python-version`); `pyproject.toml` allows `>=3.10`. Prefer `uv`.

```bash
# Set up the dev environment (editable install with dev extras)
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"

# Run — zero-arg auto-detects base (origin/main→origin/master→origin/develop→main→master→develop), diffs current branch:
uv run main.py
# Explicit range / piped diff / saved file:
.venv/bin/python main.py --range origin/main...HEAD --branch "$(git branch --show-current)"
git diff origin/main | .venv/bin/python main.py --format markdown
.venv/bin/python main.py --diff-file changes.diff --ticket-id PRD-1 --format json
# Useful flags: --model --region --format{markdown,json} --no-write --context-lines N

# Lint + format check + security scan (the CI `lint` gate — run before pushing)
.venv/bin/ruff check .
.venv/bin/ruff format          # or `ruff format --check .` to match CI
uvx bandit -r -ll agent main.py   # CI scans shipped source only (skips tests/)

# Tests (pytest, all use a fake/stub executor — no AWS or network needed)
.venv/bin/pytest
.venv/bin/pytest tests/test_loop.py::test_loop_returns_valid_report   # single test
```

> Note: a working `tests/` suite exists and runs offline against stubbed executors — run it.
> (CI does not run pytest; the `lint` gate is ruff + bandit only, so tests are your local
> responsibility.) `bandit` lives in the `[dependency-groups] dev` group, separate from the
> `[project.optional-dependencies] dev` extras (`pytest`, `ruff`) installed by `.[dev]`.

A successful CLI run exits **0** (non-zero = a required section failed validation), prints the
decorated MR, and writes `output/mr_report.{md,json}` + `output/agent_trace.json`.

### Offline smoke test (no AWS)

Inject a stub client into `BedrockExecutor(client=...)` whose `.converse()` returns a canned JSON
payload, then call `loop.run(diff, executor=...)`. See README "Validate it worked" and the
`_FakeExecutor` pattern in `tests/test_loop.py`.

## CI / release

`.github/workflows/build.yml` runs a `lint` gate first (ruff check + `ruff format --check` +
`bandit -r -ll`); `build` `needs: lint`, so any lint/format/security regression fails the
pipeline before packaging. `build` then builds wheel+sdist, runs `twine check`, and verifies a
clean-venv wheel install exposes the `pr-decorator` CLI and ships the packaged prompt. On `v*` tags it
publishes to PyPI via **Trusted Publishing** (OIDC, no stored tokens) and cuts a GitHub Release.
Release = bump `version` in `pyproject.toml`, then `git tag vX.Y.Z && git push origin vX.Y.Z`.