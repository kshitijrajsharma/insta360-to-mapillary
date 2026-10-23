import datetime
import json
import subprocess
from pathlib import Path

import exiv2
import imageio_ffmpeg
import pytest
from mapillary_tools.exif_write import ExifEdit

from insta360_to_mapillary.recordings import Recording
from insta360_to_mapillary.upload import (
    FrameOptions,
    ProcessingError,
    Trim,
    build_process_command,
    check_processed_frames,
    frames_folder_for,
    prepare_frames,
    remove_frames_outside,
    tag_panoramas,
    trim_window,
)

START = datetime.datetime(2026, 10, 17, 5, 57, 48, tzinfo=datetime.UTC)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def write_descriptions(folder: Path, error_types: list[str | None]) -> Path:
    descriptions = [
        {"filename": f"/frames/street_v_{index:06d}.jpg"}
        | ({"error": {"type": error_type, "message": "-"}} if error_type else {})
        for index, error_type in enumerate(error_types, start=1)
    ]
    description_file = folder / "mapillary_image_description.json"
    description_file.write_text(json.dumps(descriptions))
    return description_file


def test_frames_outside_track_or_duplicated_are_accepted(tmp_path: Path) -> None:
    description_file = write_descriptions(
        tmp_path,
        ["MapillaryOutsideGPXTrackError", None, "MapillaryDuplicationError", None, None],
    )

    assert check_processed_frames(description_file) == 3


def test_unexpected_frame_error_raises_naming_the_frame(tmp_path: Path) -> None:
    description_file = write_descriptions(tmp_path, [None, "MapillaryGeoTaggingError"])

    with pytest.raises(ProcessingError, match="street_v_000002.jpg: MapillaryGeoTaggingError"):
        check_processed_frames(description_file)


def test_no_placeable_frame_raises(tmp_path: Path) -> None:
    description_file = write_descriptions(
        tmp_path, ["MapillaryOutsideGPXTrackError", "MapillaryOutsideGPXTrackError"]
    )

    with pytest.raises(ProcessingError, match="No frame"):
        check_processed_frames(description_file)


def write_blank_jpg(frame: Path) -> None:
    frame.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=64x32", "-frames:v", "1"]
        + [str(frame)],
        check=True,
    )


def write_frame_at(frame: Path, captured: datetime.datetime) -> None:
    """Stamps the frame the way mapillary_tools sample_video does."""
    write_blank_jpg(frame)
    exif_edit = ExifEdit(frame)
    exif_edit.add_date_time_original(captured)
    exif_edit.add_gps_datetime(captured)
    exif_edit.write()


def write_frames(folder: Path, offsets_seconds: list[float]) -> None:
    for index, offset_seconds in enumerate(offsets_seconds, start=1):
        captured = START + datetime.timedelta(seconds=offset_seconds)
        write_frame_at(folder / f"street_v_{index:06d}.jpg", captured)


def test_frames_outside_trim_window_are_removed_keeping_both_edges(tmp_path: Path) -> None:
    folder = tmp_path / "frames" / "street.mp4"
    write_frames(folder, [0, 2, 4, 5, 6, 8, 10])

    removed_count = remove_frames_outside(
        tmp_path / "frames",
        START + datetime.timedelta(seconds=4),
        START + datetime.timedelta(seconds=8),
    )

    assert removed_count == 3
    assert sorted(path.name for path in folder.iterdir()) == [
        "street_v_000003.jpg",
        "street_v_000004.jpg",
        "street_v_000005.jpg",
        "street_v_000006.jpg",
    ]


def test_trim_removing_every_frame_raises(tmp_path: Path) -> None:
    write_frames(tmp_path / "frames" / "street.mp4", [0, 2])

    with pytest.raises(ProcessingError, match="removed every frame"):
        remove_frames_outside(
            tmp_path / "frames",
            START + datetime.timedelta(seconds=3),
            START + datetime.timedelta(seconds=9),
        )


def test_frame_without_capture_time_raises(tmp_path: Path) -> None:
    write_blank_jpg(tmp_path / "frames" / "street.mp4" / "street_v_000001.jpg")

    with pytest.raises(ProcessingError, match="no capture time"):
        remove_frames_outside(tmp_path / "frames", START, START)


def test_trim_window_leaves_out_start_and_end_seconds() -> None:
    keep_from, keep_until = trim_window(START, datetime.timedelta(seconds=10), Trim(4, 3))

    assert keep_from == START.replace(second=52)
    assert keep_until == START.replace(second=55)


def test_panorama_tags_mark_frame_as_full_equirectangular(tmp_path: Path) -> None:
    frame = tmp_path / "frames_ü" / "street.mp4" / "street_v_000001.jpg"
    write_blank_jpg(frame)

    tag_panoramas(tmp_path / "frames_ü")

    image = exiv2.ImageFactory.open(str(frame))
    image.readMetadata()
    tags = {datum.key(): datum.toString() for datum in image.xmpData()}
    assert tags == {
        "Xmp.GPano.ProjectionType": "equirectangular",
        "Xmp.GPano.UsePanoramaViewer": "True",
        "Xmp.GPano.FullPanoWidthPixels": "64",
        "Xmp.GPano.FullPanoHeightPixels": "32",
        "Xmp.GPano.CroppedAreaImageWidthPixels": "64",
        "Xmp.GPano.CroppedAreaImageHeightPixels": "32",
        "Xmp.GPano.CroppedAreaLeftPixels": "0",
        "Xmp.GPano.CroppedAreaTopPixels": "0",
    }


def write_north_track(recording: Recording) -> None:
    """About 11 metres due north over ten seconds, starting at START."""
    recording.track.write_text(
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
        '<trkpt lat="28.2816" lon="83.7422"><time>2026-10-17T05:57:48Z</time></trkpt>'
        '<trkpt lat="28.2817" lon="83.7422"><time>2026-10-17T05:57:58Z</time></trkpt>'
        "</trkseg></trk></gpx>"
    )


def read_descriptions(recording: Recording) -> list[dict]:
    description_file = recording.video.parent / "street_frames" / "mapillary_image_description.json"
    return sorted(json.loads(description_file.read_text()), key=lambda entry: entry["filename"])


def test_processed_frames_record_camera_make_and_model(tmp_path: Path) -> None:
    recording = Recording(video=tmp_path / "street.mp4", track=tmp_path / "street.gpx")
    write_north_track(recording)
    write_frames(tmp_path / "street_frames" / "street.mp4", [1])

    subprocess.run(
        build_process_command(frames_folder_for(recording), recording.track, "Insta360", "X6"),
        check=True,
    )

    description = read_descriptions(recording)[0]
    assert "error" not in description
    assert (description["MAPDeviceMake"], description["MAPDeviceModel"]) == ("Insta360", "X6")


def write_turning_track(recording: Recording) -> None:
    """About 2.2 metres per second north for two seconds, then east."""
    recording.track.write_text(
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
        '<trkpt lat="28.28160" lon="83.74220"><time>2026-10-17T05:57:48Z</time></trkpt>'
        '<trkpt lat="28.28164" lon="83.74220"><time>2026-10-17T05:57:50Z</time></trkpt>'
        '<trkpt lat="28.28164" lon="83.742245"><time>2026-10-17T05:57:52Z</time></trkpt>'
        "</trkseg></trk></gpx>"
    )


@pytest.mark.parametrize(
    ("min_spacing_meters", "expected_errors"),
    [
        (None, [None, None, None, None]),
        (3, [None, "MapillaryDuplicationError", None, "MapillaryDuplicationError"]),
    ],
)
def test_min_spacing_drops_frames_near_previous_kept_frame_in_any_direction(
    tmp_path: Path, min_spacing_meters: float | None, expected_errors: list[str | None]
) -> None:
    recording = Recording(video=tmp_path / "street.mp4", track=tmp_path / "street.gpx")
    write_turning_track(recording)
    write_frames(tmp_path / "street_frames" / "street.mp4", [0, 1, 2, 3])

    subprocess.run(
        build_process_command(
            frames_folder_for(recording), recording.track, min_spacing_meters=min_spacing_meters
        ),
        check=True,
    )

    errors = [entry.get("error", {}).get("type") for entry in read_descriptions(recording)]
    assert errors == expected_errors


def test_prepare_frames_samples_trims_tags_and_geotags_a_video(tmp_path: Path) -> None:
    recording = Recording(video=tmp_path / "street.mp4", track=tmp_path / "street.gpx")
    write_north_track(recording)
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=64x32:duration=10:rate=5"]
        + ["-metadata", "creation_time=2026-10-17T05:57:48Z", str(recording.video)],
        check=True,
    )

    ready_count = prepare_frames(
        recording,
        frames_folder_for(recording),
        FrameOptions(
            sample_interval_seconds=1,
            trim=Trim(3, 2),
            camera_make="GoPro",
            camera_model="X6",
        ),
    )

    descriptions = read_descriptions(recording)
    capture_times = [entry["MAPCaptureTime"] for entry in descriptions]
    assert capture_times[0] == "2026_10_17_05_57_51_000"
    assert capture_times[-1] == "2026_10_17_05_57_56_000"
    assert ready_count == len(descriptions)
    assert {(entry["MAPDeviceMake"], entry["MAPDeviceModel"]) for entry in descriptions} == {
        ("GoPro", "X6")
    }


def test_trim_longer_than_video_raises_before_sampling(tmp_path: Path) -> None:
    recording = Recording(video=tmp_path / "street.mp4", track=tmp_path / "street.gpx")
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=64x32:duration=4"]
        + ["-metadata", "creation_time=2026-10-17T05:57:48Z", str(recording.video)],
        check=True,
    )

    with pytest.raises(ProcessingError, match="together exceed"):
        prepare_frames(recording, frames_folder_for(recording), FrameOptions(trim=Trim(3, 2)))
    assert not frames_folder_for(recording).exists()
