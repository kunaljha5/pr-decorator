# pr-decorator

Generate structured, high-quality Pull Request descriptions from git diffs using AWS Bedrock.

---

## Overview

`pr-decorator` is a CLI tool that analyzes your git changes and produces a standardized Pull Request (PR/MR) description using an agentic workflow.

It follows a structured loop:

```
OBSERVE → PLAN → EXECUTE → VALIDATE → OUTPUT
```

The output is a clean, consistent PR description that is ready to paste into GitHub or GitLab.

---

## Features

* Generates structured PR descriptions from git diffs
* Classifies changes into features, fixes, chores, and risks
* Enforces a consistent PR template across teams
* Uses AWS Bedrock for model inference
* Supports Markdown and JSON output formats
* Includes validation and retry logic

---

## Why AWS Bedrock?

This project uses AWS Bedrock as the inference backend.

* Runs within your AWS environment (no external API dependency)
* Supports multiple foundation models (Claude, Titan, Llama)
* Uses IAM-based authentication (no API keys required)
* Fits naturally into AWS-native workflows

---

## Example Output

### Input (git diff)

```diff
+ Added authentication middleware
- Fixed token validation bug
```

### Output

```md
MR Title: Add authentication middleware and fix token validation

MR Description:

Purpose:
Improve authentication reliability and security

Summary:
Ticket | Feature | Bug Fix | Chore | Breaking | Risk
—      |   ✓     |   ✓     |       |          | LOW

Code Changes:
- Added middleware for request authentication
- Updated token validation logic

Bug Fixes:
- Fixed incorrect token parsing edge case

Risks:
- Low risk; changes are isolated to auth flow
```

---

## Installation

### Using pip

```bash
pip install pr-decorator
```

### Using uv

```bash
uv pip install pr-decorator
```

### Using pipx (recommended)

```bash
pipx install pr-decorator
```

---

## Prerequisites

* Python 3.10+
* Git installed
* AWS credentials with Bedrock access
* Access to Amazon Nova Pro model in Bedrock

---

## Configuration

Set optional environment variables:

```bash
export BEDROCK_REGION=ap-south-1
export BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0
```

Authentication uses the standard AWS credential chain.

### Config file (`.pr-decorator.yml`)

Pin per-repository defaults in a `.pr-decorator.yml` at the repo root (auto-discovered
from the working directory upward; override with `--config PATH`):

```yaml
# .pr-decorator.yml — all keys optional
model: apac.amazon.nova-pro-v1:0
region: ap-south-1
format: markdown          # markdown | json
context_lines: 100000
ticket_id: PROJ-123       # usually inferred from the branch instead
max_file_chars: 12000     # per-file prompt cap
max_total_chars: 120000   # total prompt cap
```

Precedence (highest wins): **CLI flag → `.pr-decorator.yml` → environment variable →
built-in default**. Unknown keys and bad values are warned about and ignored, never fatal.

The file is parsed by a small built-in parser, so the package stays dependency-light
(boto3 only). The schema is flat (`key: value`); for nested/advanced YAML install the
optional extra: `pip install "pr-decorator[yaml]"` (uses PyYAML when present).

---

## Usage

Run inside a git repository:

```bash
pr-decorator
```

### Common examples

```bash
# Custom range
pr-decorator --range origin/main...HEAD

# Pipe diff
git diff origin/main | pr-decorator

# Use file input
pr-decorator --diff-file changes.diff

# JSON output
pr-decorator --format json
```

---

## Output

A successful run:

* Prints the PR description to stdout
* Writes output to `output/mr_report.md` (or `.json`)
* Writes execution trace to `output/agent_trace.json`

---

## GitHub Action

Run pr-decorator automatically on every pull request and write the description
straight into the PR body — no manual CLI step. Copy
[`docs/examples/pr-decorator.yml`](docs/examples/pr-decorator.yml) into
`.github/workflows/` in your repo:

```yaml
name: PR Decorator
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write   # update the PR body
  id-token: write        # assume the AWS role via OIDC
jobs:
  decorate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0           # full history so base...head can be diffed
      - uses: kunaljha5/pr-decorator@v1
        with:
          aws-role-to-assume: ${{ vars.PR_DECORATOR_ROLE }}
          region: ap-south-1       # Bedrock region (where Nova Pro is enabled)
```

### Inputs

| Input | Default | Description |
|---|---|---|
| `model` | CLI/env default | Bedrock model id. |
| `region` | env / `ap-south-1` | AWS region for Bedrock. |
| `format` | `markdown` | `markdown` or `json`. |
| `context-lines` | `100000` | `git diff --unified` context lines. |
| `config-file` | auto-discover | Path to a `.pr-decorator.yml`. |
| `aws-role-to-assume` | — | IAM role ARN assumed via OIDC (needs `id-token: write`). |
| `aws-region` | `us-east-1` | Region used for OIDC credential exchange. |
| `github-token` | `${{ github.token }}` | Token to read/update the PR. |
| `overwrite` | `false` | `true` replaces the whole body; else merge within markers. |
| `mode` | `body` | `body` (edit PR body) or `comment` (sticky comment). |
| `markers` | `pr-decorator` | Marker namespace → `<!-- {markers}:start/end -->`. |
| `pr-decorator-version` | latest | Pin a release for reproducibility; `source` installs the action checkout. |

**Outputs:** `report-path`, `risk-level`, `updated`.

### No-clobber updates

By default the action writes the generated description **between markers**
(`<!-- pr-decorator:start -->` … `<!-- pr-decorator:end -->`). Anything you type
outside that block is preserved on re-runs; only the block is refreshed. Set
`overwrite: true` to replace the entire body instead. The PR title is never changed.

### AWS authentication (OIDC, recommended)

The action assumes an IAM role via GitHub's OIDC provider — no long-lived keys in
secrets. Create a role whose trust policy allows `token.actions.githubusercontent.com`:

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike": { "token.actions.githubusercontent.com:sub": "repo:<OWNER>/<REPO>:*" }
  }
}
```

Attach a permissions policy granting `bedrock:InvokeModel` on the Nova Pro model, then
pass the role ARN as `aws-role-to-assume` (e.g. via a repo variable).

### Notes & limitations

* **Forks:** pull requests from forks get a read-only token and no OIDC, so the body
  update and AWS auth won't work on the plain `pull_request` event. Use
  `pull_request_target` if you need fork coverage — pr-decorator only *reads* the diff
  text and never executes PR code, but review the security implications first.
* **Avoid loops:** the action edits the PR body, so don't subscribe to the `edited`
  event. Updates are idempotent (re-running yields an identical body), and the sample
  workflow also guards on the sender being the bot.

---

## How It Works

The system follows an agent loop:

### 1. Observe

* Reads git diff, commits, branch, and metadata

### 2. Plan

* Classifies changes (feature, fix, chore, docs)
* Determines required PR sections

### 3. Execute

* Calls AWS Bedrock to generate content

### 4. Validate

* Ensures format, completeness, and correctness
* Retries failed sections

### 5. Output

* Produces final PR description

---

## PR Template

The generated output follows a fixed structure:

* Title
* Purpose
* Summary table
* Code Changes
* Features Added
* Bug Fixes
* Breaking Changes
* Chores
* Docs & Linting
* Risks

Empty sections are automatically omitted.

---

## Architecture

```
Git Diff → CLI → Agent Loop → AWS Bedrock → Validation → Output
```

---

## Development

Clone the repository and install in editable mode:

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

Run:

```bash
pr-decorator --help
ruff check .
pytest
```

---

## CI/CD

The project includes GitHub Actions for:

* Building package artifacts
* Validating installation
* Publishing to PyPI (via trusted publishing)
* Creating GitHub releases

---

## Publishing

To release a new version:

```bash
git tag v0.1.1
git push origin v0.1.1
```

This triggers automated build and publish workflows.

---

## Requirements

* Stateless execution per run
* Strict adherence to PR template
* Retry logic for Bedrock failures
* Output validation before completion

---

## GitHub App (preview)

A webhook-driven GitHub App is scaffolded under [`app/`](app/) and documented in
[`docs/github-app.md`](docs/github-app.md). It would react to PR webhooks server-side
and reuse the exact decoration core in-process. **It is a non-deployed preview skeleton**,
not a running service — see the doc for the architecture, auth flow, and rollout notes.

---

## Roadmap

* ✅ GitHub Action integration (see "GitHub Action")
* ✅ PR auto-posting via GitHub API (the Action writes the PR body)
* 🚧 GitHub App (preview skeleton — see "GitHub App")
* VS Code extension
* Support for additional models

---

## License

MIT
