# GitHub App (preview / non-production)

> **Status: preview skeleton.** The code under [`app/`](../app/) is a documented
> scaffold, not a deployed service. It exists to show how a webhook-driven GitHub
> App would wrap pr-decorator, and to keep that surface honest by reusing the
> exact decoration core. Do not point production traffic at it as-is.

## Why an App in addition to the Action?

The [GitHub Action](../README.md#github-action) is the recommended path for most
teams — no hosting, OIDC for AWS, per-repo opt-in. A GitHub App makes sense when
you want **central, server-side** behavior across many repos without each one
adding a workflow file: org-wide rollout, a single place for rate-limit/cost
policy, or reacting to events the Action can't see.

## Architecture

```
PR event ──webhook──▶ App server (app/webhook.py)
                         │  1. verify X-Hub-Signature-256 (HMAC, real)
                         │  2. mint App JWT, exchange for installation token (app/auth.py)
                         ▼
                      app/decorate.py
                         │  3. GET PR diff (media type vnd.github.v3.diff) + PR body
                         │  4. agent.loop.run(diff, ...)            ← SAME core as CLI/Action
                         │  5. agent.render.to_markdown(report)
                         │  6. agent.github.merge_pr_body(...)      ← SAME marker merge
                         ▼
                      PATCH /repos/{repo}/pulls/{n}  (body)
```

The only App-specific code is transport (webhook verification, auth, HTTP I/O).
All decoration and PR-body logic is imported from the published package, so the
App and Action can never drift.

## Authentication flow

1. **App JWT** — sign a short-lived (≤10 min) RS256 JWT with the App's private
   key (`app.auth.app_jwt`). Proves identity as the App.
2. **Installation token** — exchange the JWT at
   `POST /app/installations/{id}/access_tokens` for a token scoped to one
   installation, valid ~1 hour (`app.auth.installation_token`). All PR reads/writes
   use this token.

No long-lived user tokens. AWS Bedrock credentials are a separate concern — the
server would use an instance/task IAM role (the standard boto3 chain the core
already relies on), never static keys.

## Webhook security

`app.webhook.verify_signature` performs a constant-time HMAC-SHA256 check of the
raw request body against `X-Hub-Signature-256` using the App's webhook secret.
This is implemented for real (stdlib only) because it is the security boundary;
everything else in the skeleton is a stub. Only `pull_request` actions
`opened`, `synchronize`, `reopened` are handled — `edited` is deliberately
excluded so the App's own body edit cannot trigger a loop (the same stance as the
Action, and `merge_pr_body` is idempotent regardless).

## Rate limiting & cost control

- **GitHub API:** installation tokens carry per-installation REST limits. Respect
  `Retry-After` / `X-RateLimit-Remaining` with exponential backoff; coalesce rapid
  `synchronize` events (debounce per PR) so a fast-typing pusher doesn't fan out
  N Bedrock calls.
- **Bedrock cost:** bound prompt size with `max_file_chars` / `max_total_chars`
  (now first-class settings — see [Configuration](../README.md#config-file-pr-decoratoryml)),
  skip draft PRs, and skip PRs whose head SHA was already decorated.

## Observability

`agent.loop.run` returns a `DecorationResult` whose `.trace` (an `AgentTrace`) records
every phase — the same structure the CLI writes to `output/agent_trace.json`. The
App should persist this per delivery (keyed by repo + PR + head SHA) as its primary
debugging surface, alongside the GitHub webhook delivery id.

## Multi-repo / org rollout

Install the App once at the org level and select repositories (or "all repos").
Per-repo behavior still comes from each repo's `.pr-decorator.yml`, which
`agent.config` reads — so policy stays in the repos while transport stays central.
Default org-wide behavior (model, region, overwrite vs. no-clobber) lives in the
server config and is overridden per-repo by the config file.

## Running the skeleton locally (for development only)

```bash
pip install -e ".[app]"
# Implement the stubbed token exchange / event loop first, then:
uvicorn app.webhook:build_app --factory --reload
```

The `[app]` extra (FastAPI, uvicorn, PyJWT, httpx) is **not** part of the core
install and the `app/` package is **not** shipped in the published wheel.
