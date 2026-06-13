# PREVIEW SKELETON — not deployed, not production. See docs/github-app.md.
"""Preview scaffold for a webhook-driven GitHub App wrapping pr-decorator.

This package is intentionally NOT shipped in the published wheel (it is excluded
from `[tool.setuptools] packages`) and NOT imported by the test suite. It exists
to document and sketch the App delivery surface, which reuses the *same* core as
the CLI and the GitHub Action: `agent.loop.run` + `agent.render.to_markdown` +
`agent.github.merge_pr_body`.

Optional runtime deps (web framework, JWT, HTTP client) live behind the
`pr-decorator[app]` extra; the core package stays boto3-only.
"""
