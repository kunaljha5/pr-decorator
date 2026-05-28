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

## Local Setup — Build & Validate

### 1. Prerequisites
- Python **3.12** (see `.python-version`).
- [`uv`](https://docs.astral.sh/uv/) (recommended) or plain `venv` + `pip`.
- AWS credentials with Bedrock access in your target region, and **model access
  to Amazon Nova Pro enabled** in the Bedrock console
  (*Bedrock → Model access → Nova Pro*).

### 2. Build (create venv + install)

With `uv`:
```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

Or with stock Python:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure AWS

Auth uses the standard credential chain — **never hardcode keys**. Any of:
```bash
aws configure                  # writes ~/.aws/credentials + config
# or
aws sso login --profile <p> && export AWS_PROFILE=<p>
# or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
```

Optional overrides (defaults shown):
```bash
export BEDROCK_REGION=ap-south-1
export BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0
```

Verify credentials + Bedrock reachability before running the agent:
```bash
.venv/bin/python -c "import boto3; print(boto3.client('sts', region_name='ap-south-1').get_caller_identity()['Account'])"
```

### 4. Run

```bash
# Zero-arg: auto-detect base (origin/main → main → master), diff the current
# branch against it, and auto-fill branch + commit messages. Just run:
uv run main.py
# (or: .venv/bin/python main.py)

# Override the range / branch / ticket explicitly:
.venv/bin/python main.py --range origin/main...HEAD --branch "$(git branch --show-current)"

# Or pipe any diff in:
git diff origin/main | .venv/bin/python main.py --format markdown

# From a saved diff file, JSON output, with an explicit ticket:
.venv/bin/python main.py --diff-file changes.diff --ticket-id PRD-1 --format json
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
- writes `output/mr_report.md` (or `.json`) **and** `output/agent_trace.json`.

Check the trace to confirm the Bedrock call landed — look for an `execute`
entry with `"ok": true` and a `finish` entry with `"ok": true`:
```bash
cat output/agent_trace.json
```

Smoke-test the full loop **offline** (no AWS needed) with a stubbed client:
```bash
.venv/bin/python - <<'PY'
from agent import loop, render
from agent.execute import BedrockExecutor

class Stub:
    def converse(self, **kw):
        payload = '{"title":"Add feature","sections":{"Purpose":"x","Ticket ID":"PRD-1","Code Changes":"y","Features Added":"","Linting Fixed":"","Bug Fixed":""}}'
        return {"output": {"message": {"content": [{"text": payload}]}}}

res = loop.run("diff --git a/f b/f\n+x\n", executor=BedrockExecutor(client=Stub()), branch="feat/PRD-1")
print(render.to_markdown(res.report))
print("ok:", res.validation.ok)
PY
```

> **Note:** Per project policy there are no unit tests to execute; validation
> is done by running the agent and inspecting the output + trace as above.

---

## Success Criteria

- [ ] Agent correctly classifies all change types from a git diff
- [ ] All MR template fields are populated in every run
- [ ] AWS Bedrock is called correctly with proper auth
- [ ] Agent loop retries on failure before giving up
- [ ] Final output is valid Markdown ready to paste into GitLab/GitHub MR