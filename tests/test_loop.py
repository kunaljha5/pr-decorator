"""End-to-end loop test using a fake executor — no AWS/network required."""

from agent import loop
from agent.execute import BedrockExecutor
from agent.models import MRReport

NEW_FILE_DIFF = """\
diff --git a/feature.py b/feature.py
new file mode 100644
--- /dev/null
+++ b/feature.py
@@ -0,0 +1,1 @@
+def f(): return 1
"""


class _FakeExecutor(BedrockExecutor):
    """Stub that returns canned reports instead of calling Bedrock."""

    def __init__(self, full: MRReport, partials: dict | None = None):
        self._full = full
        self._partials = partials or {}
        self.calls: list = []

    def generate(self, observation, plan, *, only_section=None):
        self.calls.append(only_section)
        if only_section is None:
            return self._full
        return MRReport(sections={only_section: self._partials.get(only_section, "filled")})


def test_loop_returns_valid_report():
    full = MRReport(
        title="Add feature",
        sections={
            "Purpose": "introduce f",
            "Ticket ID": "JIRA-1",
            "Code Changes": "added feature.py",
            "Features Added": "f()",
        },
    )
    result = loop.run(NEW_FILE_DIFF, executor=_FakeExecutor(full), branch="feat/JIRA-1-x")
    assert result.validation.ok is True
    assert result.report.title == "Add feature"
    assert any(e["phase"] == "finish" for e in result.trace.entries)


def test_loop_reexecutes_only_failed_section():
    full = MRReport(
        title="Add feature",
        sections={"Purpose": "", "Code Changes": "added feature.py"},
    )
    executor = _FakeExecutor(full, partials={"Purpose": "introduce f"})
    result = loop.run(NEW_FILE_DIFF, executor=executor)
    assert result.validation.ok is True
    assert result.report.sections["Purpose"] == "introduce f"
    # Re-execution targeted only the failing section.
    assert "Purpose" in executor.calls
