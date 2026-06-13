# PREVIEW SKELETON — not deployed, not production. See docs/github-app.md.
"""The reuse core: fetch a PR's diff, decorate it, write the result back.

This is the whole point of the App skeleton — it proves the delivery surface is
thin. The Action shells out to the CLI; the App calls the SAME functions
in-process:
  `agent.loop.run` -> `agent.render.to_markdown` -> `agent.github.merge_pr_body`.
No decoration logic is duplicated here.
"""

from __future__ import annotations

from agent import loop, render
from agent.github import DEFAULT_END, DEFAULT_START, merge_pr_body

GITHUB_API = "https://api.github.com"


def decorate_diff(
    diff: str,
    *,
    branch: str | None = None,
    commit_messages: list[str] | None = None,
    ticket_id: str | None = None,
    existing_title: str | None = None,
    existing_description: str | None = None,
) -> str:
    """Run the core loop on a diff and return the rendered Markdown MR body.

    Pure and dependency-free (no GitHub I/O), so this part is unit-testable
    offline exactly like the CLI — inject a stub executor via `loop.run`.
    """
    result = loop.run(
        diff,
        branch=branch,
        commit_messages=commit_messages,
        ticket_id=ticket_id,
        existing_title=existing_title,
        existing_description=existing_description,
    )
    # `result.trace` (DecorationResult.trace) is the observability surface —
    # persist it per-installation for debugging (see docs/github-app.md).
    return render.to_markdown(result.report)


def decorate_and_update(
    *, repo: str, pr_number: int, token: str, overwrite: bool = False
) -> None:  # pragma: no cover
    """Fetch the PR diff + body, decorate, and PATCH the PR body via the API.

    Skeleton: needs `httpx` from the `[app]` extra. The body merge reuses the
    identical `merge_pr_body` the Action uses, so manual edits outside the
    markers survive here too.
    """
    try:
        import httpx
    except ImportError as exc:
        raise NotImplementedError("install pr-decorator[app] (httpx) for live PR updates") from exc

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    base = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"

    # The diff comes from the same endpoint with the diff media type.
    diff = httpx.get(
        base, headers={**headers, "Accept": "application/vnd.github.v3.diff"}, timeout=30
    ).text
    pr = httpx.get(base, headers=headers, timeout=10).json()

    generated = decorate_diff(
        diff,
        branch=pr.get("head", {}).get("ref"),
        existing_title=pr.get("title"),
        existing_description=pr.get("body"),
    )
    merged = merge_pr_body(
        pr.get("body"),
        generated,
        overwrite=overwrite,
        start_marker=DEFAULT_START,
        end_marker=DEFAULT_END,
    )
    httpx.patch(base, headers=headers, json={"body": merged}, timeout=10).raise_for_status()
