from agent.execute import _parse_report
from agent.validate import validate


def test_parse_coerces_array_sections_to_strings():
    # The model may emit bullet sections as JSON arrays — these must not crash
    # downstream phases that call `.strip()` on section values.
    raw = """
    {
      "title": "Fix base detection",
      "risk_level": "Medium",
      "sections": {
        "Purpose": "why",
        "Ticket ID": "T-1",
        "Code Changes": ["did x", "did y"],
        "Bug Fixes": ["one thing; another thing"]
      }
    }
    """
    report = _parse_report(raw)
    assert all(isinstance(v, str) for v in report.sections.values())
    # Each array item is preserved as its own bullet (not re-split on ';').
    assert report.sections["Bug Fixes"] == "- one thing; another thing"
    assert report.sections["Code Changes"] == "- did x\n- did y"
    # And validation runs without AttributeError.
    assert validate(report).ok is True


def test_parse_tolerates_string_sections():
    raw = '{"title": "Add x", "sections": {"Purpose": "p", "Code Changes": "c"}}'
    report = _parse_report(raw)
    assert report.sections["Code Changes"] == "c"


def test_parse_handles_non_dict_sections():
    raw = '{"title": "Add x", "sections": null}'
    report = _parse_report(raw)
    assert report.sections == {}
