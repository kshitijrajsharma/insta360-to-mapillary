from pathlib import Path

import pytest

from insta360_mapillary.cli import main, resolve_options
from insta360_mapillary.upload import FrameOptions, Trim


def write_config(tmp_path: Path, text: str) -> Path:
    config = tmp_path / "rides.yaml"
    config.write_text(text)
    return config


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--skip-start", "-5", "must be a finite number, zero or more"),
        ("--skip-end", "nan", "must be a finite number, zero or more"),
        ("--sample-interval", "0", "must be a finite number above zero"),
        ("--min-spacing", "-1", "must be a finite number above zero"),
        ("--camera-make", " ", "must not be blank"),
        ("--camera-model", " ", "must not be blank"),
    ],
)
def test_invalid_option_value_is_rejected(
    option: str, value: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        resolve_options(["rides", option, value])
    assert message in capsys.readouterr().err


def test_command_line_overrides_config_which_overrides_defaults(tmp_path: Path) -> None:
    config = write_config(tmp_path, "folder: rides\nskip_start: 30\ncamera_model: X6\n")

    options = resolve_options(["--config", str(config), "--skip-start", "114"])

    assert options.folder == tmp_path / "rides"
    assert options.skip_start == 114
    assert options.camera_model == "X6"
    assert options.sample_interval == 2.0


def test_missing_folder_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = write_config(tmp_path, "camera_model: X6\n")

    with pytest.raises(SystemExit):
        resolve_options(["--config", str(config)])
    assert "give a folder" in capsys.readouterr().err


def test_config_error_is_reported_through_the_parser(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = write_config(tmp_path, "skip_strat: 114\n")

    with pytest.raises(SystemExit):
        resolve_options(["--config", str(config)])
    assert "Unknown keys" in capsys.readouterr().err


def test_per_video_trim_wins_over_config_trim(tmp_path: Path) -> None:
    config = write_config(
        tmp_path,
        "folder: rides\nskip_start: 30\nskip_end: 5\nrecordings:\n  street: {skip_start: 114}\n",
    )
    options = resolve_options(["--config", str(config)])

    assert options.frame_options_for("street").trim == Trim(114, 5)
    assert options.frame_options_for("market").trim == Trim(30, 5)


def test_frame_options_carry_spacing_interval_and_camera(tmp_path: Path) -> None:
    config = write_config(tmp_path, "folder: rides\nmin_spacing: 3\ncamera_model: X6\n")
    options = resolve_options(["--config", str(config), "--sample-interval", "1"])

    assert options.frame_options_for("street") == FrameOptions(
        sample_interval_seconds=1, min_spacing_meters=3, camera_model="X6"
    )


def test_command_line_trim_wins_over_per_video_trim(tmp_path: Path) -> None:
    config = write_config(
        tmp_path, "folder: rides\nrecordings:\n  street: {skip_start: 114, skip_end: 9}\n"
    )
    options = resolve_options(["--config", str(config), "--skip-start", "10"])

    assert options.frame_options_for("street").trim == Trim(10, 9)


def test_missing_config_file_is_reported_through_the_parser(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        resolve_options(["--config", str(tmp_path / "absent.yaml")])
    assert "absent.yaml" in capsys.readouterr().err


def test_no_dry_run_overrides_config_dry_run(tmp_path: Path) -> None:
    config = write_config(tmp_path, "folder: rides\ndry_run: true\n")

    assert resolve_options(["--config", str(config), "--no-dry-run"]).dry_run is False


def test_recordings_naming_a_missing_video_stops_before_processing(tmp_path: Path) -> None:
    for name in ["street.mp4", "street.gpx"]:
        (tmp_path / name).touch()
    config = write_config(tmp_path, "folder: .\nrecordings:\n  market: {skip_start: 1}\n")

    with pytest.raises(SystemExit, match="market"):
        main(["--config", str(config)])


def test_video_without_gpx_exits_naming_the_video(tmp_path: Path) -> None:
    (tmp_path / "street.mp4").touch()

    with pytest.raises(SystemExit, match="street.mp4"):
        main([str(tmp_path)])


def test_folder_without_videos_exits_with_message(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="No .mp4 files"):
        main([str(tmp_path)])
