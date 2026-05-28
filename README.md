# PR Decorator Agent — Primary Instructions

## Project Overview
An agentic AI system powered by **AWS Bedrock** that automatically decorates Pull Requests (Merge Requests) by following a structured observe → plan → execute → observe loop, and generates a standardized MR report as output.

---

## Agent Loop (Core Behavior)

```
OBSERVE → PLAN → EXECUTE → OBSERVE → (if outcome OK) → FINISH & GENERATE OUTPUT
```

| Phase       | Description |
|-------------|-------------|
| **Observe** | Read the raw diff, commits, branch name, ticket references, and any existing MR metadata |
| **Plan**    | Decide what sections need to be filled, what code changes occurred, what categories they fall into |
| **Execute** | Call AWS Bedrock (Claude/Titan/etc.) to generate each section of the MR description |
| **Observe** | Validate the generated output — check for completeness, correctness, and formatting |
| **Finish**  | If output passes validation, finalize and post/return the decorated MR |

---

## MR Output Template

```
MR Title        : <concise, imperative-mood title>
MR Description  :
  Purpose       : <why this MR exists — business/technical reason>
  Ticket ID     : <linked issue/ticket e.g. JIRA-123>
  Code Changes  : <summary of what files/modules changed and how>
  Features Added: <new capabilities introduced, if any>
  Linting Fixed : <style/formatting/lint issues resolved, if any>
  Bug Fixed     : <bugs resolved with brief description, if any>
```

---

## Primary Instructions for the Agent

### 1. Input Collection (Observe Phase)
- Accept a **git diff** or list of changed files as primary input
- Accept optional metadata: branch name, commit messages, linked ticket ID
- Accept optional: existing MR title/description (for enrichment mode)

### 2. Analysis & Planning (Plan Phase)
- Parse the diff to classify changes:
  - New files → Features Added
  - Modified logic → Code Changes or Bug Fixed
  - Formatting/style-only changes → Linting Fixed
  - Config/dependency changes → Code Changes
- Extract ticket ID from branch name or commit message (e.g. `feat/JIRA-123-...`)
- Infer the purpose from commit messages and change patterns

### 3. Generation (Execute Phase)
- Call **AWS Bedrock** with a structured prompt per section
- Use a system prompt that enforces the MR template format
- Generate each section independently or in a single structured call
- Keep descriptions concise, technical, and developer-friendly

### 4. Validation (Observe Phase — Post Execute)
- Check all required fields are populated (no empty sections)
- Ensure Ticket ID is present (warn if missing)
- Ensure MR Title follows imperative mood convention (e.g. "Add", "Fix", "Refactor")
- If any section is empty or invalid → re-plan and re-execute that section only

### 5. Output Generation (Finish Phase)
- Output the final decorated MR as:
  - Markdown string (for GitLab/GitHub MR body)
  - Optionally: JSON payload for API submission
- Log a brief agent trace: what was observed, planned, executed, and validated

---

## AWS Bedrock Integration

- **Model**: Amazon **Nova Pro** via Bedrock. Default model id is the APAC
  cross-region inference profile `apac.amazon.nova-pro-v1:0` (required to call
  Nova in `ap-south-1`). Override with the `BEDROCK_MODEL_ID` env var or the
  `--model` flag (e.g. `amazon.nova-pro-v1:0` / `us.amazon.nova-pro-v1:0` in US regions).
- **Invocation**: Uses `bedrock-runtime` → `converse` API (model-agnostic).
- **Prompt Strategy**: Strict output-format enforcement via `prompts/mr_template.txt`.
- **Region**: Configurable. Default `ap-south-1`; override with `BEDROCK_REGION` /
  `AWS_REGION` env var or the `--region` flag.
- **Auth**: IAM Role / AWS credential chain (no hardcoded keys).

---

## Non-Functional Requirements

- The agent must be **stateless** — each PR decoration is an independent run
- Support **retry logic** (max 2 retries) if Bedrock call fails
- Output must always conform to the MR template — no freeform deviation
- Agent trace/log must be saved alongside output for debugging

---

## File Structure (Suggested)

```
pr-decorator/
├── instruction.md          ← this file
├── agent/
│   ├── observe.py          ← diff parsing & input collection
│   ├── plan.py             ← change classification & section planning
│   ├── execute.py          ← AWS Bedrock call & prompt management
│   ├── validate.py         ← output validation logic
│   └── loop.py             ← orchestrates observe→plan→execute→observe
├── prompts/
│   └── mr_template.txt     ← system prompt with MR template
├── output/
│   └── mr_report.md        ← generated MR decoration output
└── main.py                 ← entry point
```

---

## Installation & Usage

### 1. Prerequisites
- Python **3.10+**.
- `git` on your `PATH` (the CLI shells out to it to read diffs).
- AWS credentials with Bedrock access in your target region, and **model access
  to Amazon Nova Pro enabled** in the Bedrock console
  (*Bedrock → Model access → Nova Pro*).

### 2. Install

Install the published package — this puts the `pr-decorator` command on your `PATH`:

```bash
pip install pr-decorator
# or, with uv:
uv pip install pr-decorator
# or run without installing into your environment:
uvx pr-decorator --help
```

To keep it isolated from your other tools, install it via [`pipx`](https://pipx.pypa.io/):
```bash
pipx install pr-decorator
```

Confirm it's available:
```bash
pr-decorator --help
```

### 3. Configure AWS

Auth uses the standard AWS credential chain — **never hardcode keys**. Use any of:
```bash
aws configure                  # writes ~/.aws/credentials + config
# or
aws sso login --profile <p> && export AWS_PROFILE=<p>
# or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
```

Optional environment overrides (defaults shown):
```bash
export BEDROCK_REGION=ap-south-1
export BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0
```

Verify credentials + region reach AWS before running the agent:
```bash
python -c "import boto3; print(boto3.client('sts', region_name='ap-south-1').get_caller_identity()['Account'])"
```

### 4. Run

Run `pr-decorator` from inside the git repository whose changes you want to decorate:

```bash
# Zero-arg: auto-detect base (origin/main → main → master), diff the current
# branch against it, and auto-fill branch + commit messages. Just run:
pr-decorator

# Override the range / branch / ticket explicitly:
pr-decorator --range origin/main...HEAD --branch "$(git branch --show-current)"

# Or pipe any diff in:
git diff origin/main | pr-decorator --format markdown

# From a saved diff file, JSON output, with an explicit ticket:
pr-decorator --diff-file changes.diff --ticket-id PRD-1 --format json
```

Useful flags: `--model`, `--region`, `--format {markdown,json}`, `--no-write`
(print only, skip writing to `output/`), `--context-lines N` (context lines for
`git diff --unified` on `--range`; the large default feeds whole-file content to
the LLM so it can judge intent — lower it for very large PRs). Content size is
capped via `MR_MAX_FILE_CHARS` / `MR_MAX_TOTAL_CHARS` env vars.

### 5. Validate it worked

A successful run:
- exits with code **0** (non-zero means a required section failed validation),
- prints the decorated MR to stdout, and
- writes `output/mr_report.md` (or `.json`) **and** `output/agent_trace.json`
  in the current working directory.

Check the trace to confirm the Bedrock call landed — look for an `execute`
entry with `"ok": true` and a `finish` entry with `"ok": true`:
```bash
cat output/agent_trace.json
```

> **Missing AWS credentials?** If no credentials resolve from the chain, the run
> stops immediately (it does **not** retry) with a clear message —
> `error: AWS credentials are missing. ...` — and exits with code `2`.

### Develop from source

Contributing to `pr-decorator` itself? Clone the repo and use an editable install
(Python 3.12 recommended — see `.python-version`):

```bash
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
.venv/bin/pr-decorator --help        # the CLI, from your checkout
.venv/bin/ruff check .               # lint
.venv/bin/pytest                     # offline test suite (stubbed Bedrock, no AWS)
```

---

## CI / CD — Build, Package & Publish

The `.github/workflows/build.yml` workflow runs on every push, PR, and version
tag:

- **build** — builds the wheel + sdist with `uv build`, validates metadata with
  `twine check`, installs the wheel into a clean venv to confirm the
  `pr-decorator` CLI and packaged prompt work, and uploads `dist/*` as a
  downloadable artifact.
- **publish-pypi** *(tags `v*` only)* — publishes to PyPI via **Trusted
  Publishing** (OIDC; no API tokens stored).
- **release** *(tags `v*` only)* — attaches the artifacts to a GitHub Release.

### Publishing to PyPI

The package is published to <https://pypi.org/project/pr-decorator/>.

**One-time setup — register the GitHub repo as a Trusted Publisher on PyPI:**

1. Log in to PyPI → *Your projects* → **pr-decorator** → *Settings* →
   *Publishing* (for a brand-new name, use *Publishing* → *Add a pending
   publisher* first).
2. Add a GitHub Actions publisher:
   - **Owner:** `kunaljha5`
   - **Repository:** `pr-decorator`
   - **Workflow name:** `build.yml`
   - **Environment:** `pypi`
3. In the GitHub repo, create an **Environment** named `pypi`
   (*Settings → Environments → New environment*) — optionally add required
   reviewers to gate releases.

**Cut a release:**

```bash
# bump version in pyproject.toml first (e.g. 0.1.0 -> 0.1.1), commit, then:
git tag v0.1.1
git push origin v0.1.1
```

The tag triggers build → publish-pypi → release. After it succeeds:

```bash
pip install pr-decorator        # or: uv pip install pr-decorator
pr-decorator --help
```

> To dry-run against **TestPyPI** first, add a Trusted Publisher on
> <https://test.pypi.org> and set `repository-url:
> https://test.pypi.org/legacy/` on the `pypa/gh-action-pypi-publish` step.
>
> Manual publish without CI (needs a PyPI API token):
> `uv build && uvx twine upload dist/*`.

---

## Success Criteria

- [ ] Agent correctly classifies all change types from a git diff
- [ ] All MR template fields are populated in every run
- [ ] AWS Bedrock is called correctly with proper auth
- [ ] Agent loop retries on failure before giving up
- [ ] Final output is valid Markdown ready to paste into GitLab/GitHub MR