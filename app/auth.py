# PREVIEW SKELETON — not deployed, not production. See docs/github-app.md.
"""GitHub App authentication: App JWT -> short-lived installation token.

A GitHub App authenticates in two hops:
  1. Sign a short (<=10 min) JWT with the App's RSA private key (proves "I am
     this App").
  2. Exchange the JWT for an *installation* access token scoped to one repo/org
     installation (proves "I may act on this installation"). That token is what
     the API calls in `decorate.py` use, and it expires in ~1 hour.

The crypto/HTTP deps (PyJWT, httpx) are in the `pr-decorator[app]` extra and are
imported lazily so importing this module never requires them.
"""

from __future__ import annotations

GITHUB_API = "https://api.github.com"


def app_jwt(app_id: str, private_key_pem: str, *, now: int | None = None, ttl: int = 540) -> str:
    """Return a signed App JWT (RS256). `now` is epoch seconds (injectable for tests).

    Skeleton: requires `pyjwt[crypto]` from the `[app]` extra.
    """
    try:
        import jwt  # PyJWT
    except ImportError as exc:  # pragma: no cover - skeleton guard
        raise NotImplementedError("install pr-decorator[app] (PyJWT) to mint App JWTs") from exc

    if now is None:  # pragma: no cover - skeleton; real code injects a clock
        import time

        now = int(time.time())
    payload = {"iat": now - 60, "exp": now + ttl, "iss": app_id}
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def installation_token(app_jwt_token: str, installation_id: int) -> str:  # pragma: no cover
    """Exchange an App JWT for an installation access token.

    Skeleton: POST /app/installations/{id}/access_tokens with the JWT as a
    bearer token; the response `token` field is the installation token. Requires
    `httpx` from the `[app]` extra.
    """
    try:
        import httpx
    except ImportError as exc:
        raise NotImplementedError("install pr-decorator[app] (httpx) to exchange tokens") from exc

    resp = httpx.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]
