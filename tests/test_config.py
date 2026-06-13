"""Offline tests for `.pr-decorator.yml` loading and CLI precedence."""

import argparse

import pytest

import main
from agent import config


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_none_path_is_empty():
    cfg = config.load_config(None)
    assert cfg == config.Config()
    assert cfg.warnings == []


def test_load_known_keys(tmp_path):
    path = _write(
        tmp_path,
        ".pr-decorator.yml",
        "model: us.amazon.nova-pro-v1:0\n"
        "region: us-east-1\n"
        "format: json\n"
        "context_lines: 50\n"
        "max_file_chars: 2000\n"
        "ticket_id: PROJ-9\n",
    )
    cfg = config.load_config(path)
    assert cfg.model == "us.amazon.nova-pro-v1:0"
    assert cfg.region == "us-east-1"
    assert cfg.format == "json"
    assert cfg.context_lines == 50
    assert cfg.max_file_chars == 2000
    assert cfg.ticket_id == "PROJ-9"
    assert cfg.warnings == []


def test_comments_and_quotes(tmp_path):
    path = _write(
        tmp_path,
        ".pr-decorator.yml",
        '# leading comment\nmodel: "amazon.nova-pro-v1:0"  # inline comment\n\nformat: markdown\n',
    )
    cfg = config.load_config(path)
    assert cfg.model == "amazon.nova-pro-v1:0"
    assert cfg.format == "markdown"


def test_unknown_keys_warn_not_raise(tmp_path):
    path = _write(tmp_path, ".pr-decorator.yml", "model: m\nbogus: 1\noverwrite: true\n")
    cfg = config.load_config(path)
    assert cfg.model == "m"
    assert any("bogus" in w for w in cfg.warnings)
    assert any("overwrite" in w for w in cfg.warnings)


def test_bad_int_warns_and_drops(tmp_path):
    path = _write(tmp_path, ".pr-decorator.yml", "context_lines: abc\n")
    cfg = config.load_config(path)
    assert cfg.context_lines is None
    assert any("context_lines" in w for w in cfg.warnings)


def test_bad_format_warns_and_drops(tmp_path):
    path = _write(tmp_path, ".pr-decorator.yml", "format: xml\n")
    cfg = config.load_config(path)
    assert cfg.format is None
    assert any("format" in w for w in cfg.warnings)


def test_explicit_missing_file_raises():
    with pytest.raises(config.ConfigError):
        config.find_config_file(explicit="/nonexistent/.pr-decorator.yml")


def test_non_mapping_document_raises(tmp_path):
    path = _write(tmp_path, ".pr-decorator.yml", "- just\n- a\n- list\n")
    with pytest.raises(config.ConfigError):
        config.load_config(path)


def test_nested_yaml_rejected_by_minimal_parser(tmp_path, monkeypatch):
    # Force the vendored parser path (simulate PyYAML being absent).
    monkeypatch.setattr(config, "_parse_yaml", config._parse_yaml_minimal)
    path = _write(tmp_path, ".pr-decorator.yml", "model: m\nnested:\n  key: value\n")
    with pytest.raises(config.ConfigError):
        config.load_config(path)


def test_find_prefers_yml_over_yaml(tmp_path):
    _write(tmp_path, ".pr-decorator.yml", "model: from-yml\n")
    _write(tmp_path, ".pr-decorator.yaml", "model: from-yaml\n")
    found = config.find_config_file(start=tmp_path)
    assert found is not None and found.name == ".pr-decorator.yml"


def test_find_walks_up(tmp_path):
    _write(tmp_path, ".pr-decorator.yml", "model: m\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    found = config.find_config_file(start=nested)
    assert found is not None and found.parent == tmp_path


def test_find_returns_none_when_absent(tmp_path):
    assert config.find_config_file(start=tmp_path) is None


# --- precedence: CLI flag > config file > built-in default ----------------


def _args(**overrides):
    base = dict(
        model=None,
        region=None,
        ticket_id=None,
        format=None,
        context_lines=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_resolve_cli_beats_config():
    cfg = config.Config(format="json", context_lines=10, model="cfg-model")
    settings = main._resolve_settings(
        _args(format="markdown", context_lines=5, model="cli-model"), cfg
    )
    assert settings["format"] == "markdown"
    assert settings["context_lines"] == 5
    assert settings["model"] == "cli-model"


def test_resolve_config_beats_default():
    cfg = config.Config(format="json", context_lines=42, max_file_chars=999)
    settings = main._resolve_settings(_args(), cfg)
    assert settings["format"] == "json"
    assert settings["context_lines"] == 42
    assert settings["max_file_chars"] == 999


def test_resolve_falls_back_to_builtin_defaults():
    settings = main._resolve_settings(_args(), config.Config())
    assert settings["format"] == "markdown"
    assert settings["context_lines"] == 100000
    # Unset model/region stay None so BedrockExecutor applies its env/default.
    assert settings["model"] is None
    assert settings["region"] is None
    assert settings["max_file_chars"] is None
