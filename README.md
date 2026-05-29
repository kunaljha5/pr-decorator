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

## Roadmap

* GitHub Action integration
* VS Code extension
* PR auto-posting via GitHub API
* Support for additional models

---

## License

MIT
