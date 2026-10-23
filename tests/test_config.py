from pathlib import Path

import pytest

from insta360_to_mapillary.config import ConfigError, load_config


def load(tmp_path: Path, text: str) -> dict:
    config = tmp_path / "rides.yaml"
    config.write_text(text)
    return load_config(config)


def test_full_config_loads_with_folder_relative_to_file(tmp_path: Path) -> None:
    config = load(
        tmp_path,
        "folder: rides\n"
        "user_name: mapper\n"
        "sample_interval: 2\n"
        "skip_start: 114\n"
        "skip_end: 6\n"
        "min_spacing: 3\n"
        "camera_make: Insta360\n"
        "camera_model: X6\n"
        "dry_run: true\n"
        "recordings:\n"
        "  street: {skip_start: 120, skip_end: 4}\n",
    )

    assert config == {
        "folder": tmp_path / "rides",
        "user_name": "mapper",
        "sample_interval": 2,
        "skip_start": 114,
        "skip_end": 6,
        "min_spacing": 3,
        "camera_make": "Insta360",
        "camera_model": "X6",
        "dry_run": True,
        "recordings": {"street": {"skip_start": 120, "skip_end": 4}},
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- folder\n", "must contain a mapping"),
        ("skip_strat: 114\n", "Unknown keys in .*: skip_strat"),
        ("skip_start: -1\n", "skip_start must be a finite number, zero or more"),
        ("skip_start: .inf\n", "skip_start must be a finite number, zero or more"),
        ("skip_start: true\n", "skip_start has the wrong type"),
        ("sample_interval: 0\n", "sample_interval must be a finite number above zero"),
        ("camera_model: 6\n", "camera_model has the wrong type"),
        ("min_spacing: 0\n", "min_spacing must be a finite number above zero"),
        ("recordings:\n  street: {skip_end: -2}\n", "recordings.street.skip_end must be"),
        ("dry_run: yes please\n", "dry_run must be true or false"),
        ("recordings:\n  street: {skip_strat: 1}\n", "Unknown keys in recordings.street"),
        ("recordings: [street]\n", "recordings must map video names"),
        ("recordings:\n  street: 114\n", "recordings.street must be a mapping"),
        ("recordings:\n  street: {skip_start: -1}\n", "recordings.street.skip_start must be"),
        (
            "recordings:\n  20261017: {skip_start: 5}\n",
            "recordings key 20261017 must be a video name",
        ),
    ],
)
def test_invalid_config_raises_naming_the_key(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load(tmp_path, text)
