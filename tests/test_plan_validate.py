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
