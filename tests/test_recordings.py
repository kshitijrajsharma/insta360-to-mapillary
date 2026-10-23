from pathlib import Path

import pytest

from insta360_mapillary.recordings import MissingTrackError, Recording, find_recordings


def test_pairs_each_video_with_same_named_gpx(tmp_path: Path) -> None:
    for name in ["ride_b.mp4", "ride_b.gpx", "ride_a.mp4", "ride_a.gpx", "notes.txt"]:
        (tmp_path / name).touch()

    assert find_recordings(tmp_path) == [
        Recording(video=tmp_path / "ride_a.mp4", track=tmp_path / "ride_a.gpx"),
        Recording(video=tmp_path / "ride_b.mp4", track=tmp_path / "ride_b.gpx"),
    ]


def test_video_without_gpx_raises_naming_the_video(tmp_path: Path) -> None:
    for name in ["ride_a.mp4", "ride_a.gpx", "ride_b.mp4", "other.gpx"]:
        (tmp_path / name).touch()

    with pytest.raises(MissingTrackError, match="ride_b.mp4") as error:
        find_recordings(tmp_path)
    assert "ride_a.mp4" not in str(error.value)


def test_folder_without_videos_raises(tmp_path: Path) -> None:
    (tmp_path / "track.gpx").touch()

    with pytest.raises(FileNotFoundError, match="No .mp4 files"):
        find_recordings(tmp_path)
