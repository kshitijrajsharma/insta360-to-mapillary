import subprocess
from pathlib import Path

import pytest

from insta360_mapillary.camera import read_camera_make


@pytest.fixture
def blank_video(tmp_path: Path) -> Path:
    video = tmp_path / "street.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=64x32:duration=1", str(video)],
        check=True,
    )
    return video


@pytest.fixture
def insta360_video(blank_video: Path) -> Path:
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-XMP-GSpherical:StitchingSoftware=Insta360",
            str(blank_video),
        ],
        check=True,
    )
    return blank_video


def test_insta360_stitched_video_reads_as_insta360(insta360_video: Path) -> None:
    assert read_camera_make(insta360_video) == "Insta360"


def test_video_without_stitching_software_has_no_make(blank_video: Path) -> None:
    assert read_camera_make(blank_video) is None
