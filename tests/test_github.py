"""Offline tests for the marker-merge helper and the pr-decorator-merge CLI."""

from agent import github
from agent.github import DEFAULT_END, DEFAULT_START, extract_block, merge_pr_body

GEN = "Generated description.\n- point one\n- point two"


def _block(content=GEN):
    return f"{DEFAULT_START}\n{content}\n{DEFAULT_END}"


def test_empty_body_returns_bare_block():
    assert merge_pr_body("", GEN) == _block()
    assert merge_pr_body(None, GEN) == _block()
    assert merge_pr_body("   \n  ", GEN) == _block()


def test_overwrite_replaces_everything():
    existing = "manual text\n" + _block("old") + "\nmore manual"
    assert merge_pr_body(existing, GEN, overwrite=True) == _block()


def test_markers_present_replaces_only_inside_and_preserves_outside():
    existing = f"## Manual heading\nkeep me\n\n{_block('old content')}\n\nfooter note"
    merged = merge_pr_body(existing, GEN)
    assert "## Manual heading" in merged
    assert "keep me" in merged
    assert "footer note" in merged
    assert "old content" not in merged
    assert extract_block(merged) == GEN.strip()


def test_markers_absent_appends_block():
    existing = "Some manual PR body the author wrote."
    merged = merge_pr_body(existing, GEN)
    assert merged.startswith("Some manual PR body the author wrote.")
    assert merged.rstrip().endswith(DEFAULT_END)
    assert extract_block(merged) == GEN.strip()


def test_idempotent_rerun():
    existing = "manual\n\n" + _block()
    once = merge_pr_body(existing, GEN)
    twice = merge_pr_body(once, GEN)
    assert once == twice


def test_malformed_markers_treated_as_absent():
    # end before start, and a lone start — both must not corrupt the body.
    reversed_markers = f"text {DEFAULT_END} middle {DEFAULT_START} tail"
    merged = merge_pr_body(reversed_markers, GEN)
    assert reversed_markers in merged  # original preserved
    assert merged.rstrip().endswith(DEFAULT_END)

    lone_start = f"prefix {DEFAULT_START} no end here"
    merged2 = merge_pr_body(lone_start, GEN)
    assert lone_start in merged2


def test_extract_block_variants():
    assert extract_block(None) is None
    assert extract_block("no markers") is None
    assert extract_block(f"{DEFAULT_END}before{DEFAULT_START}") is None  # out of order
    assert extract_block(_block("hi")) == "hi"


def test_custom_markers():
    start, end = github.markers_for("custom")
    body = merge_pr_body("", GEN, start_marker=start, end_marker=end)
    assert body == f"{start}\n{GEN.strip()}\n{end}"
    assert extract_block(body, start, end) == GEN.strip()


# --- pr-decorator-merge CLI round-trip ------------------------------------


def test_cli_merges_to_outfile(tmp_path, capsys):
    existing = tmp_path / "existing.md"
    existing.write_text("manual top\n", encoding="utf-8")
    generated = tmp_path / "gen.md"
    generated.write_text(GEN, encoding="utf-8")
    out = tmp_path / "out.md"

    rc = github._cli(
        [
            "--existing-file",
            str(existing),
            "--generated-file",
            str(generated),
            "--out-file",
            str(out),
        ]
    )
    assert rc == 0
    merged = out.read_text(encoding="utf-8")
    assert merged.startswith("manual top")
    assert extract_block(merged) == GEN.strip()


def test_cli_no_existing_to_stdout(tmp_path, capsys):
    generated = tmp_path / "gen.md"
    generated.write_text(GEN, encoding="utf-8")

    rc = github._cli(["--generated-file", str(generated)])
    assert rc == 0
    out = capsys.readouterr().out
    assert out == _block()


def test_cli_custom_markers_and_overwrite(tmp_path, capsys):
    existing = tmp_path / "existing.md"
    existing.write_text("dropped on overwrite\n", encoding="utf-8")
    generated = tmp_path / "gen.md"
    generated.write_text(GEN, encoding="utf-8")

    rc = github._cli(
        [
            "--existing-file",
            str(existing),
            "--generated-file",
            str(generated),
            "--markers",
            "mybot",
            "--overwrite",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert out == f"<!-- mybot:start -->\n{GEN.strip()}\n<!-- mybot:end -->"
    assert "dropped on overwrite" not in out
