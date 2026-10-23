from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

TEXT_KEYS = {"user_name", "camera_make", "camera_model"}
POSITIVE_KEYS = {"sample_interval", "min_spacing"}
TRIM_KEYS = {"skip_start", "skip_end"}
KNOWN_KEYS = TEXT_KEYS | POSITIVE_KEYS | TRIM_KEYS | {"folder", "dry_run", "recordings"}


class ConfigError(Exception):
    pass


def check_non_negative(number: float) -> float:
    if not (0 <= number < float("inf")):
        raise ValueError(f"must be a finite number, zero or more: {number}")
    return number


def check_positive(number: float) -> float:
    if not (0 < number < float("inf")):
        raise ValueError(f"must be a finite number above zero: {number}")
    return number


def check_text(text: str) -> str:
    if not text.strip():
        raise ValueError("must not be blank")
    return text


def load_config(path: Path) -> dict[str, Any]:
    """Relative folder paths count from the config file's own folder."""
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ConfigError(f"{path} must contain a mapping of option names to values")
    check_keys(config, KNOWN_KEYS, str(path))

    for key in TEXT_KEYS & config.keys():
        config[key] = check_value(config[key], str, check_text, key)
    for key in POSITIVE_KEYS & config.keys():
        config[key] = check_value(config[key], (int, float), check_positive, key)
    for key in TRIM_KEYS & config.keys():
        config[key] = check_value(config[key], (int, float), check_non_negative, key)
    if "dry_run" in config and not isinstance(config["dry_run"], bool):
        raise ConfigError("dry_run must be true or false")
    if "folder" in config:
        folder = Path(check_value(config["folder"], str, check_text, "folder")).expanduser()
        config["folder"] = path.parent / folder
    if "recordings" in config:
        config["recordings"] = check_recordings(config["recordings"])
    return config


def check_recordings(recordings: object) -> dict[str, dict[str, float]]:
    if not isinstance(recordings, dict):
        raise ConfigError("recordings must map video names to their options")
    for name, options in recordings.items():
        if not isinstance(name, str):
            raise ConfigError(f"recordings key {name!r} must be a video name; quote it")
        if not isinstance(options, dict):
            raise ConfigError(f"recordings.{name} must be a mapping of options")
        check_keys(options, TRIM_KEYS, f"recordings.{name}")
        for key in TRIM_KEYS & options.keys():
            options[key] = check_value(
                options[key], (int, float), check_non_negative, f"recordings.{name}.{key}"
            )
    return recordings


def check_keys(mapping: dict, allowed: set[str], location: str) -> None:
    unknown = sorted(str(key) for key in mapping.keys() - allowed)
    if unknown:
        raise ConfigError(f"Unknown keys in {location}: {', '.join(unknown)}")


def check_value(
    value: Any, expected: type | tuple[type, ...], check: Callable[[Any], Any], key: str
) -> Any:
    # YAML true/false load as bool, which Python also treats as an int
    if isinstance(value, bool) or not isinstance(value, expected):
        raise ConfigError(f"{key} has the wrong type: {value!r}")
    try:
        return check(value)
    except ValueError as error:
        raise ConfigError(f"{key} {error}") from error
