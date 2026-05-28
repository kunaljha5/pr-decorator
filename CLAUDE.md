# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: Pre-implementation

This repo currently contains **only a design specification** — there is no source code, build system, or tests yet. `README.md` is the authoritative spec for the system to be built. The Python `.gitignore` signals the intended implementation language; no `pyproject.toml`/`requirements.txt`/`main.py` exists yet. When implementing, you are creating these from scratch — follow the structure and contracts described below and in the README rather than discovering them from existing code.

## What this project is

**PR Decorator Agent** — an agentic system (Python + AWS Bedrock) that takes a git diff plus optional metadata and produces a standardized Merge Request report. It runs a single-pass agent loop:

```
OBSERVE → PLAN → EXECUTE → OBSERVE (validate) → FINISH
```

The loop is the core architecture, and each phase maps to a module (see suggested layout in README under "File Structure"):

- **Observe** (`agent/observe.py`) — collect inputs: git diff/changed files (primary), plus optional branch name, commit messages, linked ticket ID, and an existing MR title/description (enrichment mode).
- **Plan** (`agent/plan.py`) — classify each change into MR template sections: new files → *Features Added*; modified logic → *Code Changes* or *Bug Fixed*; formatting-only → *Linting Fixed*; config/deps → *Code Changes*. Extract ticket ID from branch/commit (e.g. `feat/JIRA-123-...`); infer purpose from commit messages.
- **Execute** (`agent/execute.py`) — call AWS Bedrock to generate each section. Holds prompt management; system prompt lives in `prompts/mr_template.txt` and must enforce the output template.
- **Observe/Validate** (`agent/validate.py`) — check all required fields populated, ticket ID present (warn if missing), title in imperative mood. If a section is empty/invalid, **re-plan and re-execute that section only**.
- **Loop** (`agent/loop.py`) — orchestrates the phases. Entry point is `main.py`.

## Hard contracts (do not deviate)

These are requirements from the spec, not suggestions:

- **Output must always conform to the MR template** (see README "MR Output Template") — no freeform deviation. Sections: Purpose, Ticket ID, Code Changes, Features Added, Linting Fixed, Bug Fixed.
- **Stateless** — each PR decoration is an independent run; carry no state between runs.
- **Retry logic** — max 2 retries on Bedrock call failure.
- **Agent trace** must be logged/saved alongside output (what was observed/planned/executed/validated) for debugging.
- Final output is Markdown (for GitHub/GitLab MR body); optionally a JSON payload for API submission.

## AWS Bedrock integration

- Primary model: Claude 3 via Bedrock.
- Use the `bedrock-runtime` client — `invoke_model` or `converse` API.
- Region configurable, default `ap-south-1`.
- **Auth via IAM role / AWS credential chain — never hardcode keys.**

## Tests

**NO TESTS CASES TO IMPLEMENT OR EXECUTE**
