from agent.models import ChangeCategory, MRReport
from agent.observe import observe
from agent.plan import plan
from agent.validate import validate

NEW_FILE_DIFF = """\
diff --git a/feature.py b/feature.py
new file mode 100644
--- /dev/null
+++ b/feature.py
@@ -0,0 +1,1 @@
+def f(): return 1
"""

DOC_DIFF = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,1 +1,1 @@
-old usage
+new usage
"""


def test_plan_routes_new_file_to_features_added():
    p = plan(observe(NEW_FILE_DIFF))
    assert ChangeCategory.FEATURES_ADDED.value in p.sections
    assert "feature.py" in p.sections[ChangeCategory.FEATURES_ADDED.value]


def test_plan_routes_docs_to_docs_and_linting():
    p = plan(observe(DOC_DIFF))
    assert ChangeCategory.DOCS_LINTING.value in p.sections
    assert "README.md" in p.sections[ChangeCategory.DOCS_LINTING.value]
    assert ChangeCategory.FEATURES_ADDED.value not in p.sections


def test_validate_flags_empty_required_section():
    report = MRReport(title="Add feature", sections={"Purpose": "", "Code Changes": ""})
    result = validate(report)
    assert result.ok is False
    assert "Purpose" in result.failed_sections


def test_validate_warns_on_missing_ticket_but_passes():
    report = MRReport(
        title="Add feature",
        sections={"Purpose": "x", "Code Changes": "y", "Ticket ID": ""},
    )
    result = validate(report)
    assert result.ok is True
    assert any("Ticket ID" in w for w in result.warnings)


def test_validate_warns_on_non_imperative_title():
    report = MRReport(
        title="Added a feature",
        sections={"Purpose": "x", "Code Changes": "y"},
    )
    result = validate(report)
    assert any("imperative" in w for w in result.warnings)


def test_validate_warns_on_file_name_leak_in_code_changes():
    report = MRReport(
        title="Add feature",
        sections={
            "Purpose": "x",
            "Code Changes": "- Updated loop.py and README.md to add retries",
        },
    )
    result = validate(report)
    # A leak never fails the run (exit stays 0) but does flag the section for
    # re-execution with corrective feedback so a retry can converge.
    assert result.ok is True
    leak_warnings = [w for w in result.warnings if "file names/paths" in w]
    assert len(leak_warnings) == 1
    assert "loop.py" in leak_warnings[0]
    assert "README.md" in leak_warnings[0]
    assert "Code Changes" in result.failed_sections
    assert "loop.py" in result.section_feedback["Code Changes"]


def test_validate_allows_doc_names_in_docs_and_linting():
    report = MRReport(
        title="Update docs",
        sections={
            "Purpose": "x",
            "Code Changes": "- Reworked the agent loop control flow",
            "Docs & Linting": "- Updated README.md and applied ruff formatting",
        },
    )
    result = validate(report)
    # Naming a document/tool in Docs & Linting is fine — no leak warning at all.
    assert not any("file" in w.lower() for w in result.warnings)


def test_validate_flags_source_paths_in_docs_and_linting():
    report = MRReport(
        title="Update docs",
        sections={
            "Purpose": "x",
            "Code Changes": "- Reworked the agent loop control flow",
            # Test files are not docs — they belong in Chores, and the raw path
            # must not appear even in the section that may name documents.
            "Docs & Linting": "- Added tests/test_execute.py and test_render.py",
        },
    )
    result = validate(report)
    assert result.ok is True
    leak_warnings = [w for w in result.warnings if "source/test file paths" in w]
    assert len(leak_warnings) == 1
    assert "test_execute.py" in leak_warnings[0]
    assert "test_render.py" in leak_warnings[0]
    # Flagged for re-execution even though it's the file-naming-allowed section.
    assert "Docs & Linting" in result.failed_sections


def test_validate_does_not_flag_clean_conceptual_bullets():
    report = MRReport(
        title="Refactor loop",
        sections={
            "Purpose": "x",
            "Code Changes": "- Threaded a risk level through the agent loop",
        },
    )
    result = validate(report)
    assert not any("file names/paths" in w for w in result.warnings)
