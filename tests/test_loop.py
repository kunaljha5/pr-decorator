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
        self.feedbacks: list = []

    def generate(self, observation, plan, *, only_section=None, feedback=None):
        self.calls.append(only_section)
        self.feedbacks.append(feedback)
        if only_section is None:
            return self._full
        return MRReport(sections={only_section: self._partials.get(only_section, "filled")})


def test_loop_returns_valid_report():
    full = MRReport(
        title="Add feature",
        sections={
            "Purpose": "introduce f",
            "Ticket ID": "JIRA-1",
            "Code Changes": "added a feature function",
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
        sections={"Purpose": "", "Code Changes": "added a feature function"},
    )
    executor = _FakeExecutor(full, partials={"Purpose": "introduce f"})
    result = loop.run(NEW_FILE_DIFF, executor=executor)
    assert result.validation.ok is True
    assert result.report.sections["Purpose"] == "introduce f"
    # Re-execution targeted only the failing section.
    assert "Purpose" in executor.calls


def test_loop_reexecutes_and_fixes_file_name_leak():
    full = MRReport(
        title="Update docs",
        sections={
            "Purpose": "refresh the guides",
            "Ticket ID": "JIRA-2",
            "Code Changes": "reworked the agent loop control flow",
            # A leak: test files are not docs and must not be cited by path.
            "Docs & Linting": "added tests/test_render.py and test_execute.py",
        },
    )
    clean = "documented the new template across the README"
    executor = _FakeExecutor(full, partials={"Docs & Linting": clean})
    result = loop.run(NEW_FILE_DIFF, executor=executor)
    # The leaking section was regenerated, and with corrective feedback so a
    # temp=0 retry could actually differ from the rejected output.
    assert "Docs & Linting" in executor.calls
    assert any(f and "file path" in f for f in executor.feedbacks)
    # The final report no longer leaks; a leak never fails the run (exit stays 0).
    assert result.report.sections["Docs & Linting"] == clean
    assert result.validation.ok is True
    assert not any("file" in w.lower() for w in result.validation.warnings)
