"""`.pr-decorator.yml` configuration loading.

Lets a repository pin decoration settings (model, region, output format, diff
context size, content caps, ticket id) in a checked-in file instead of passing
flags every run. Consumed by `main.py`, which layers it under explicit CLI flags
(see `_resolve_settings`): **CLI flag > config file > env var > built-in default**.

YAML parsing: the config is intentionally *flat* (`key: value` only), so a tiny
vendored parser covers it and keeps the package dependency-free (boto3-only). If
PyYAML happens to be installed (the optional `pr-decorator[yaml]` extra), it is
used instead for full-spec robustness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_FILENAMES: tuple[str, ...] = (".pr-decorator.yml", ".pr-decorator.yaml")

# Keys the CLI understands. Anything else is warned about and ignored, so a
# typo or an Action-only key (handled in action.yml) never silently changes
# behavior or raises.
_STR_KEYS = frozenset({"model", "region", "format", "ticket_id"})
_INT_KEYS = frozenset({"context_lines", "max_file_chars", "max_total_chars"})
KNOWN_KEYS = _STR_KEYS | _INT_KEYS

_VALID_FORMATS = frozenset({"markdown", "json"})


class ConfigError(ValueError):
    """Raised when a config file exists but cannot be parsed/interpreted.

    A *missing* file is not an error (no config is a valid state); a malformed
    one is, because the user clearly intended settings that we can't honor.
    """


@dataclass
class Config:
    """Resolved settings from a `.pr-decorator.yml` (all optional = unset)."""

    model: str | None = None
    region: str | None = None
    format: str | None = None
    ticket_id: str | None = None
    context_lines: int | None = None
    max_file_chars: int | None = None
    max_total_chars: int | None = None
    # Non-fatal issues (unknown keys, bad values) surfaced to the user as
    # `warning:` lines rather than aborting the run.
    warnings: list[str] = field(default_factory=list)


def find_config_file(start: Path | None = None, explicit: str | None = None) -> Path | None:
    """Locate the config file to load.

    With `explicit` (the `--config` flag), that exact path is required — a
    missing one raises so a typo'd flag fails loudly. Otherwise walk from
    `start` (default: cwd) up to the filesystem root looking for the first of
    `DEFAULT_FILENAMES`; return None if none is found.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ConfigError(f"config file not found: {explicit}")
        return path

    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        for name in DEFAULT_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_config(path: Path | None) -> Config:
    """Parse `path` into a `Config`. A None path yields an empty Config."""
    if path is None:
        return Config()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable despite existing
        raise ConfigError(f"could not read config file {path}: {exc}") from exc

    data = _parse_yaml(text)
    if not isinstance(data, dict):
        raise ConfigError(
            f"config file {path} must be a mapping of key: value, got {type(data).__name__}"
        )

    return _build_config(data)


def _build_config(data: dict) -> Config:
    """Validate and coerce a parsed mapping into a `Config`, collecting warnings."""
    cfg = Config()
    for key, value in data.items():
        if key not in KNOWN_KEYS:
            cfg.warnings.append(f"unknown config key '{key}' ignored")
            continue
        if value is None:
            continue
        if key in _INT_KEYS:
            coerced = _coerce_int(value)
            if coerced is None:
                cfg.warnings.append(f"config key '{key}' must be an integer; ignoring {value!r}")
                continue
            setattr(cfg, key, coerced)
        else:  # string keys
            text = str(value).strip()
            if key == "format" and text not in _VALID_FORMATS:
                cfg.warnings.append(
                    f"config key 'format' must be one of {sorted(_VALID_FORMATS)}; ignoring {text!r}"
                )
                continue
            setattr(cfg, key, text)
    return cfg


def _coerce_int(value) -> int | None:
    """Best-effort int coercion; None signals an unusable value."""
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# --- YAML parsing ---------------------------------------------------------

# Scalars the vendored parser maps to Python values (PyYAML does this natively).
_BOOL_LITERALS = {"true": True, "false": False, "yes": True, "no": False, "on": True, "off": False}
_NULL_LITERALS = {"", "null", "~", "none"}


def _parse_yaml(text: str) -> dict:
    """Parse a flat `key: value` document into a dict.

    Prefers PyYAML when available; otherwise falls back to a minimal parser that
    handles exactly what `.pr-decorator.yml` needs: `key: value` pairs, `#`
    comments (whole-line and trailing on unquoted values), single/double quoted
    strings, and int/bool/null scalars. Nested structures are not supported by
    the fallback (the schema is flat) and raise `ConfigError`.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_yaml_minimal(text)

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # malformed YAML
        raise ConfigError(f"invalid YAML: {exc}") from exc
    return loaded if loaded is not None else {}


def _parse_yaml_minimal(text: str) -> dict:
    """Dependency-free fallback parser for the flat config schema."""
    result: dict[str, object] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":  # indentation implies nesting, which we don't support
            raise ConfigError(
                f"line {lineno}: nested/indented YAML is not supported by the built-in parser "
                f"(install the 'pr-decorator[yaml]' extra for full YAML): {raw!r}"
            )
        if ":" not in line:
            raise ConfigError(f"line {lineno}: expected 'key: value', got {raw!r}")
        key, _, rest = line.partition(":")
        result[key.strip()] = _parse_scalar(rest.strip())
    return result


def _parse_scalar(token: str) -> object:
    """Interpret a single unquoted/quoted scalar token into a Python value."""
    if token and token[0] in "\"'":
        quote = token[0]
        end = token.find(quote, 1)
        if end == -1:
            raise ConfigError(f"unterminated quoted string: {token!r}")
        return token[1:end]
    # Strip a trailing inline comment from an unquoted value.
    if "#" in token:
        token = token.split("#", 1)[0].strip()
    lowered = token.lower()
    if lowered in _NULL_LITERALS:
        return None
    if lowered in _BOOL_LITERALS:
        return _BOOL_LITERALS[lowered]
    try:
        return int(token)
    except ValueError:
        return token
