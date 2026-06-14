# PREVIEW SKELETON — not deployed, not production. See docs/github-app.md.
"""Webhook receiver: verify the signature, then route pull_request events.

`verify_signature` is a complete, dependency-free HMAC check (stdlib only) — the
one piece that must be correct for security, so it is real rather than a stub.
The HTTP server (`build_app`) is sketched against FastAPI from the `[app]` extra.
"""

from __future__ import annotations

import hashlib
import hmac

# pull_request actions we react to. 'edited' is excluded: the App edits the PR
# body, which would emit another 'edited' and risk a loop (mirrors the Action).
HANDLED_ACTIONS = frozenset({"opened", "synchronize", "reopened"})


def verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify GitHub's `X-Hub-Signature-256` header against the raw body.

    The header is `sha256=<hex hmac>`. Uses a constant-time compare. Returns
    False (rather than raising) for a missing/malformed header so the caller can
    respond 401 uniformly.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def should_handle(event_name: str, payload: dict) -> bool:
    """True if this is a pull_request event with an action we decorate on."""
    return event_name == "pull_request" and payload.get("action") in HANDLED_ACTIONS


def handle_event(
    event_name: str, payload: dict, *, installation_token: str
) -> None:  # pragma: no cover
    """Route a verified webhook to the decoration flow.

    Skeleton: extracts the PR coordinates and delegates to
    `app.decorate.decorate_and_update`, which reuses the core loop in-process.
    """
    if not should_handle(event_name, payload):
        return
    from .decorate import decorate_and_update

    pr = payload["pull_request"]
    repo = payload["repository"]["full_name"]
    decorate_and_update(repo=repo, pr_number=pr["number"], token=installation_token)


def build_app():  # pragma: no cover - skeleton; needs the [app] extra
    """Construct the FastAPI app. Requires `fastapi`/`uvicorn` from `[app]`."""
    try:
        from fastapi import FastAPI, Header, HTTPException, Request
    except ImportError as exc:
        raise NotImplementedError("install pr-decorator[app] (fastapi) to run the server") from exc

    import os

    app = FastAPI(title="pr-decorator (preview)")
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    @app.post("/webhook")
    async def webhook(
        request: Request,
        x_hub_signature_256: str = Header(default=None),
        x_github_event: str = Header(default=""),
    ):
        body = await request.body()
        if not verify_signature(body, x_hub_signature_256, secret):
            raise HTTPException(status_code=401, detail="bad signature")
        # Real impl: resolve the installation token (app.auth) and enqueue the
        # work so the webhook returns quickly.
        return {"ok": True, "handled": should_handle(x_github_event, await request.json())}

    return app
