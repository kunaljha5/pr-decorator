"""EXECUTE phase — AWS Bedrock call & prompt management.

Generates the MR report from a `Plan` + `Observation` by calling Bedrock's
`converse` API. The system prompt (which enforces the MR template) lives in
`prompts/mr_template.txt`. Auth comes from the standard AWS credential chain /
IAM role — never hardcode keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import MRReport, Observation, Plan

_DEFAULT_REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "ap-south-1"
# Amazon Nova Pro. In ap-south-1 (APAC) Nova is served via a cross-region
# inference profile, hence the `apac.` prefix. Override with BEDROCK_MODEL_ID
# (e.g. plain "amazon.nova-pro-v1:0" in us-east-1, or "us.amazon.nova-pro-v1:0").
_DEFAULT_MODEL_ID = os.getenv("BEDROCK_MODEL_ID") or "apac.amazon.nova-pro-v1:0"
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "mr_template.txt"


def load_system_prompt() -> str:
    """Load the MR-template system prompt from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_user_message(observation: Observation, plan: Plan, only_section: str | None) -> str:
    """Render the planned facts into a single user-turn prompt for Bedrock."""
    lines = ["Decorate the following Pull Request into the MR template.", ""]
    lines.append(f"Branch: {observation.branch or '(none)'}")
    lines.append(f"Ticket ID: {plan.ticket_id or '(none found)'}")
    if observation.commit_messages:
        lines.append("Commit messages:")
        lines += [f"  - {m}" for m in observation.commit_messages]
    lines.append("")
    lines.append("Planned sections and the changes feeding them:")
    for section, items in plan.sections.items():
        if only_section and section != only_section:
            continue
        lines.append(f"  {section}:")
        lines += [f"    - {item}" for item in items]
    if only_section:
        lines.append("")
        lines.append(f"Regenerate ONLY the '{only_section}' section as valid JSON.")
    lines.append("")
    lines.append("Raw diff:")
    lines.append(observation.diff)
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

            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def _converse(self, user_message: str) -> str:
        """Call Bedrock `converse` and return the assistant text."""
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": self._system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"temperature": 0.2, "maxTokens": 2048},
        )
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


def _parse_report(raw: str) -> MRReport:
    """Parse the model's JSON response into an `MRReport`.

    Tolerates fenced ```json blocks the model may wrap the payload in.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") : text.rfind("}") + 1]
    data = json.loads(text)
    return MRReport(title=data.get("title", ""), sections=data.get("sections", {}))
