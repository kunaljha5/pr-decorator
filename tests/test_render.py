from agent.models import MRReport
from agent.render import to_markdown


def _report(**sections):
    risk = sections.pop("risk_level", "")
    return MRReport(title="Fix base detection", risk_level=risk, sections=sections)


def test_summary_table_sits_after_purpose_and_before_body():
    md = to_markdown(_report(Purpose="why", **{"Ticket ID": "T-1", "Code Changes": "how"}))
    purpose = md.index("**Purpose**")
    table = md.index("| Ticket | Feature | Bug Fix | Chore | Breaking | Risk |")
    body = md.index("**Code Changes**")
    assert purpose < table < body
    # Ticket id now lives in the table's first column, not its own block.
    assert "**Ticket ID**" not in md
    assert "T-1" in md


def test_table_marks_derive_from_populated_sections():
    md = to_markdown(
        _report(
            Purpose="why",
            **{
                "Ticket ID": "T-1",
                "Code Changes": "how",
                "Bug Fixes": "fixed it",
                "Chores": "bumped version",
            },
        )
    )
    # Ticket leads; Feature & Breaking absent -> "—"; Bug Fix & Chore -> "✅".
    assert "| T-1 | — | ✅ | ✅ | — | Medium |" in md


def test_missing_ticket_renders_dash_in_table():
    md = to_markdown(_report(Purpose="why", **{"Ticket ID": "", "Code Changes": "how"}))
    table_row = [ln for ln in md.splitlines() if ln.startswith("| ") and "LOW" in ln][-1]
    # First data cell is the ticket; absent -> placeholder dash.
    assert table_row.split("|")[1].strip() == "—"


def test_empty_optional_sections_are_skipped():
    md = to_markdown(_report(Purpose="why", **{"Ticket ID": "T-1", "Code Changes": "how"}))
    assert "**Features Added**" not in md
    assert "**Breaking Changes**" not in md
    assert "**Chores**" not in md


def test_risk_level_uses_model_value_when_present():
    md = to_markdown(
        _report(risk_level="high", Purpose="why", **{"Ticket ID": "T-1", "Code Changes": "how"})
    )
    assert "| HIGH |" in md


def test_risk_level_falls_back_to_breaking_high():
    md = to_markdown(
        _report(
            Purpose="why",
            **{"Ticket ID": "T-1", "Code Changes": "how", "Breaking Changes": "renamed flag"},
        )
    )
    assert "| HIGH |" in md


def test_body_sections_render_as_bullets():
    md = to_markdown(
        _report(
            Purpose="why",
            **{"Ticket ID": "T-1", "Code Changes": "- did x\n- did y"},
        )
    )
    body = md.split("**Code Changes**", 1)[1]
    assert "- did x" in body and "- did y" in body
    # Purpose stays prose (no bullet marker added).
    assert "\n- why" not in md


def test_prose_blob_is_split_into_bullets():
    md = to_markdown(
        _report(
            Purpose="why",
            **{"Ticket ID": "T-1", "Code Changes": "First change. Second change."},
        )
    )
    assert "- First change." in md
    assert "- Second change." in md


def test_existing_bullet_markers_are_normalized():
    md = to_markdown(
        _report(
            Purpose="why",
            **{"Ticket ID": "T-1", "Code Changes": "* star one\n1. number two"},
        )
    )
    assert "- star one" in md
    assert "- number two" in md
    assert "* star one" not in md


def test_docs_and_linting_section_renders_as_bullets():
    md = to_markdown(
        _report(
            Purpose="why",
            **{
                "Ticket ID": "T-1",
                "Code Changes": "how",
                "Docs & Linting": "- Updated README\n- Applied ruff formatting",
            },
        )
    )
    assert "**Docs & Linting**" in md
    assert "- Updated README" in md
    assert "- Applied ruff formatting" in md


def test_chore_column_reflects_docs_and_linting():
    md_chore = to_markdown(
        _report(Purpose="p", **{"Ticket ID": "T", "Code Changes": "c", "Chores": "bumped"})
    )
    md_docs = to_markdown(
        _report(Purpose="p", **{"Ticket ID": "T", "Code Changes": "c", "Docs & Linting": "readme"})
    )
    # Both populate the single "Chore" column in the summary table.
    row_chore = [ln for ln in md_chore.splitlines() if ln.startswith("| ") and "✅" in ln][-1]
    row_docs = [ln for ln in md_docs.splitlines() if ln.startswith("| ") and "✅" in ln][-1]
    # Chore is the 4th cell now that Ticket leads the table.
    assert row_chore.split("|")[4].strip() == "✅"
    assert row_docs.split("|")[4].strip() == "✅"


def test_long_bullets_wrap_to_80_chars():
    long_point = "Reordered base detection to try origin/develop before develop " * 3
    md = to_markdown(
        _report(Purpose="why", **{"Ticket ID": "T-1", "Code Changes": long_point.strip()})
    )
    assert all(len(line) <= 80 for line in md.splitlines())
