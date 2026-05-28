from agent.observe import extract_ticket_id, observe, parse_diff

SAMPLE_DIFF = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 import os
+import sys
-old_line
diff --git a/src/new_feature.py b/src/new_feature.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/src/new_feature.py
@@ -0,0 +1,2 @@
+def feature():
+    return 1
"""


def test_extract_ticket_id_from_branch():
    assert extract_ticket_id("feat/JIRA-123-add-thing") == "JIRA-123"


def test_extract_ticket_id_prefers_first_source():
    assert extract_ticket_id(None, "ABC-9 do work", "XYZ-1") == "ABC-9"


def test_parse_diff_detects_new_file_and_counts():
    files = parse_diff(SAMPLE_DIFF)
    by_path = {f.path: f for f in files}
    assert by_path["src/new_feature.py"].is_new is True
    assert by_path["src/app.py"].is_new is False
    assert by_path["src/app.py"].added_lines == 1
    assert by_path["src/app.py"].removed_lines == 1


def test_observe_infers_ticket_from_branch():
    obs = observe(SAMPLE_DIFF, branch="bugfix/PROJ-42-thing")
    assert obs.ticket_id == "PROJ-42"
    assert len(obs.files) == 2
