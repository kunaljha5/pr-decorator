"""Orchestrates the agent loop: OBSERVE -> PLAN -> EXECUTE -> OBSERVE -> FINISH.

Stateless: each `run` is an independent decoration. On a failed Bedrock call,
retries up to `MAX_RETRIES` times. If validation fails, re-executes only the
failed sections (also bounded by retries). Emits an `AgentTrace` alongside the
final report for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import observe as observe_phase
from . import plan as plan_phase
from . import validate as validate_phase
from .execute import BedrockExecutor, MissingCredentialsError
from .models import AgentTrace, MRReport, ValidationResult

MAX_RETRIES = 2


@dataclass
class DecorationResult:
    """Final output of a loop run: the report, validation, and the trace."""

    report: MRReport
    validation: ValidationResult
    trace: AgentTrace


def _execute_with_retry(executor: BedrockExecutor, observation, plan, trace, *, only_section=None):
    """Call EXECUTE, retrying on exception up to MAX_RETRIES times."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            report = executor.generate(observation, plan, only_section=only_section)
            trace.record("execute", attempt=attempt, only_section=only_section, ok=True)
            return report
        except MissingCredentialsError as exc:
            # Non-retryable: surface immediately rather than burning retries.
            trace.record("execute", attempt=attempt, only_section=only_section, error=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001 — retry on any Bedrock/parse failure
            last_error = exc
            trace.record("execute", attempt=attempt, only_section=only_section, error=str(exc))
    raise RuntimeError(f"Bedrock execution failed after {MAX_RETRIES} retries") from last_error


def run(
    diff: str,
    *,
    executor: BedrockExecutor | None = None,
    branch: str | None = None,
    commit_messages: list[str] | None = None,
    ticket_id: str | None = None,
    existing_title: str | None = None,
    existing_description: str | None = None,
) -> DecorationResult:
    """Run one full, stateless PR decoration."""
    executor = executor or BedrockExecutor()
    trace = AgentTrace()

    # OBSERVE
    observation = observe_phase.observe(
        diff,
        branch=branch,
        commit_messages=commit_messages,
        ticket_id=ticket_id,
        existing_title=existing_title,
        existing_description=existing_description,
    )
    trace.record(
        "observe",
        files=[f.path for f in observation.files],
        ticket_id=observation.ticket_id,
    )

    # PLAN
    plan = plan_phase.plan(observation)
    trace.record("plan", sections=list(plan.sections), purpose_hint=plan.purpose_hint)

    # EXECUTE
    report = _execute_with_retry(executor, observation, plan, trace)

    # OBSERVE (validate) — re-execute only failed sections, bounded by retries.
    validation = validate_phase.validate(report)
    for attempt in range(MAX_RETRIES):
        if validation.ok or not validation.failed_sections:
            break
        trace.record("validate", attempt=attempt, errors=validation.errors)
        for section in validation.failed_sections:
            partial = _execute_with_retry(executor, observation, plan, trace, only_section=section)
            if section in partial.sections:
                report.sections[section] = partial.sections[section]
            if partial.title and not report.title:
                report.title = partial.title
        validation = validate_phase.validate(report)

    trace.record(
        "finish",
        ok=validation.ok,
        errors=validation.errors,
        warnings=validation.warnings,
    )
    return DecorationResult(report=report, validation=validation, trace=trace)
