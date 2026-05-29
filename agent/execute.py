"""EXECUTE phase — AWS Bedrock call & prompt management.

Generates the MR report from a `Plan` + `Observation` by calling Bedrock's
`converse` API. The system prompt (which enforces the MR template) lives in
`prompts/mr_template.txt`. Auth comes from the standard AWS credential chain /
IAM role — never hardcode keys.
"""

from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from .models import MRReport, Observation, Plan

_DEFAULT_REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "ap-south-1"
# Amazon Nova Pro. In ap-south-1 (APAC) Nova is served via a cross-region
# inference profile, hence the `apac.` prefix. Override with BEDROCK_MODEL_ID
# (e.g. plain "amazon.nova-pro-v1:0" in us-east-1, or "us.amazon.nova-pro-v1:0").
_DEFAULT_MODEL_ID = os.getenv("BEDROCK_MODEL_ID") or "apac.amazon.nova-pro-v1:0"
_PROMPT_NAME = "mr_template.txt"

_NO_CREDS_MESSAGE = (
    "AWS credentials are missing. The PR Decorator needs AWS credentials with "
    "Amazon Bedrock access. Configure them via one of:\n"
    "  - `aws configure`  (writes ~/.aws/credentials)\n"
    "  - `aws sso login --profile <p>` then `export AWS_PROFILE=<p>`\n"
    "  - export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (+ AWS_SESSION_TOKEN)\n"
    "  - an attached IAM role (EC2 / ECS / Lambda)"
)


class MissingCredentialsError(RuntimeError):
    """Raised when no AWS credentials are available for the Bedrock call.

    Non-retryable: retrying won't conjure credentials, so the loop surfaces this
    immediately instead of burning retries or masking it behind a generic error.
    """


def load_system_prompt() -> str:
    """Load the MR-template system prompt.

    Reads it as packaged data from the `prompts` package (so it ships in the
    wheel and resolves once installed); falls back to the repo-root file when
    running from a source checkout that isn't installed.
    """
    try:
        return (files("prompts") / _PROMPT_NAME).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        path = Path(__file__).resolve().parent.parent / "prompts" / _PROMPT_NAME
        return path.read_text(encoding="utf-8")


# Per-file and total content caps, so a huge PR can't blow the token budget.
# Nova Pro has a large context window, so these are generous; tune via env.
_MAX_PATCH_CHARS = int(os.getenv("MR_MAX_FILE_CHARS") or "12000")
_MAX_TOTAL_CHARS = int(os.getenv("MR_MAX_TOTAL_CHARS") or "120000")


def _change_kind(change) -> str:
    if change.is_new:
        return "added"
    if change.is_deleted:
        return "deleted"
    return "modified"


def _render_files(observation: Observation) -> str:
    """Render each changed file with its kind, stats, and actual content.

    Caps per-file and total size; once the budget is spent, remaining files are
    listed by name only (with a note) so nothing is silently dropped.
    """
    blocks: list[str] = []
    spent = 0
    for change in observation.files:
        kind = _change_kind(change)
        head = f"=== {change.path} [{kind}, +{change.added_lines}/-{change.removed_lines}] ==="
        body = change.patch.rstrip("\n")
        if spent >= _MAX_TOTAL_CHARS:
            blocks.append(head + "\n(content omitted — total context budget reached)")
            continue
        if len(body) > _MAX_PATCH_CHARS:
            dropped = len(body) - _MAX_PATCH_CHARS
            body = body[:_MAX_PATCH_CHARS] + f"\n... [truncated {dropped} chars of this file]"
        if not body:
            body = "(no textual content captured — likely binary or empty)"
        spent += len(body)
        blocks.append(head + "\n" + body)
    return "\n\n".join(blocks)


def _build_user_message(observation: Observation, plan: Plan, only_section: str | None) -> str:
    """Render the planned facts into a single user-turn prompt for Bedrock."""
    lines = [
        "Decorate the following Pull Request into the MR template.",
        "Read the ACTUAL CODE below and infer what the author is trying to do and",
        "why. Summarize intent — do NOT just list file names.",
        "",
    ]
    lines.append(f"Branch: {observation.branch or '(none)'}")
    lines.append(f"Ticket ID: {plan.ticket_id or '(none found)'}")
    if observation.commit_messages:
        lines.append("Commit messages:")
        lines += [f"  - {m}" for m in observation.commit_messages]
    if observation.existing_title or observation.existing_description:
        lines.append("")
        lines.append("Existing MR metadata (enrichment mode — build on, don't discard):")
        if observation.existing_title:
            lines.append(f"  Title: {observation.existing_title}")
        if observation.existing_description:
            lines.append(f"  Description: {observation.existing_description}")
    lines.append("")
    lines.append(
        "Heuristic section hints — how many files fell into each category "
        "(refine using the code; do not copy these counts into the output):"
    )
    for section, items in plan.sections.items():
        lines.append(f"  {section}: {len(items)} file(s)")
    lines.append("")
    lines.append("Changed files with their content:")
    lines.append("")
    lines.append(_render_files(observation))
    if only_section:
        lines.append("")
        lines.append(
            f"Regenerate ONLY the '{only_section}' section. Return the full JSON "
            "shape, but only that section needs meaningful content."
        )
    return "\n".join(lines)


class BedrockExecutor:
    """Wraps the bedrock-runtime client and the generation prompt.

    The client is created lazily so the rest of the loop (and tests) can run
    without AWS credentials present.
    """

    def __init__(
        self,
        *,
        region: str = _DEFAULT_REGION,
        model_id: str = _DEFAULT_MODEL_ID,
        client=None,
    ) -> None:
        self.region = region
        self.model_id = model_id
        self._client = client
        self._system_prompt = load_system_prompt()

    @property
    def client(self):
        if self._client is None:
            import boto3  # imported lazily; only needed for real invocation

            session = boto3.Session(region_name=self.region)
            if session.get_credentials() is None:
                raise MissingCredentialsError(_NO_CREDS_MESSAGE)
            self._client = session.client("bedrock-runtime")
        return self._client

    def _converse(self, user_message: str) -> str:
        """Call Bedrock `converse` and return the assistant text."""

        try:
            response = self.client.converse(
                modelId=self.model_id,
                system=[{"text": self._system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_message}]}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
            )
        except (NoCredentialsError, PartialCredentialsError) as exc:
            # Authoritative call-time signal (e.g. creds resolved but incomplete).
            raise MissingCredentialsError(_NO_CREDS_MESSAGE) from exc
        return response["output"]["message"]["content"][0]["text"]

    def generate(
        self,
        observation: Observation,
        plan: Plan,
        *,
        only_section: str | None = None,
    ) -> MRReport:
        """Generate the full report, or regenerate a single failed section.

        The model is instructed (via the system prompt) to return JSON shaped as
        {"title": str, "sections": {section_name: str, ...}}.
        """
        user_message = _build_user_message(observation, plan, only_section)
        raw = self._converse(user_message)
        return _parse_report(raw)


def _coerce_section(value) -> str:
    """Normalize a section value to a string.

    The model is asked to return bullet lists, so it may emit either a string
    (newline-separated bullets) or a JSON array of points. Arrays are joined
    one-per-line; rendering re-formats either form into wrapped bullets.
    """
    if isinstance(value, list):
        # Prefix "- " so each array item is preserved as one bullet — rendering
        # won't re-split a single item on its internal punctuation.
        return "\n".join(f"- {str(item).strip()}" for item in value if str(item).strip())
    return value if isinstance(value, str) else str(value)


def _parse_report(raw: str) -> MRReport:
    """Parse the model's JSON response into an `MRReport`.

    Tolerates fenced ```json blocks the model may wrap the payload in.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") : text.rfind("}") + 1]
    data = json.loads(text)
    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        sections = {}
    return MRReport(
        title=data.get("title", ""),
        sections={k: _coerce_section(v) for k, v in sections.items()},
        risk_level=data.get("risk_level", ""),
    )
