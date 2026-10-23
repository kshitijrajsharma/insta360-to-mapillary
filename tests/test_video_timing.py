import datetime
import subprocess
from pathlib import Path

import imageio_ffmpeg
import pytest

from insta360_to_mapillary.video_timing import (
    format_for_mapillary_tools,
    read_recording_duration,
    read_recording_start,
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def make_video(path: Path, *metadata: str) -> Path:
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=64x32:duration=1"]
        + [argument for item in metadata for argument in ("-metadata", item)]
        + [str(path)],
        check=True,
    )
    return path


def test_reads_creation_time_as_recording_start(tmp_path: Path) -> None:
    video = make_video(tmp_path / "ride.mp4", "creation_time=2026-10-17T05:57:48Z")

    assert read_recording_start(video) == datetime.datetime(
        2026, 10, 17, 5, 57, 48, tzinfo=datetime.UTC
    )


def test_video_without_creation_time_raises(tmp_path: Path) -> None:
    video = make_video(tmp_path / "ride.mp4")

    with pytest.raises(ValueError, match="no creation_time"):
        read_recording_start(video)


def test_reads_movie_duration(tmp_path: Path) -> None:
    video = make_video(tmp_path / "ride.mp4")

    assert read_recording_duration(video).total_seconds() == pytest.approx(1, abs=0.05)


def test_formats_start_in_utc_with_milliseconds() -> None:
    nepal_time = datetime.timezone(datetime.timedelta(hours=5, minutes=45))
    start = datetime.datetime(2026, 10, 17, 11, 42, 48, 508999, tzinfo=nepal_time)

    assert format_for_mapillary_tools(start) == "2026_10_17_05_57_48_508"
