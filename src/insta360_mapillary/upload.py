import datetime
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from mapillary_tools.constants import IMAGE_DESCRIPTION_FILENAME

from insta360_mapillary.camera import read_camera_make
from insta360_mapillary.recordings import Recording
from insta360_mapillary.video_timing import (
    format_for_mapillary_tools,
    read_recording_duration,
    read_recording_start,
    truncate_to_milliseconds,
)

MAPILLARY_TOOLS = [sys.executable, "-m", "mapillary_tools.commands"]
# Frames before the first or after the last GPS point, and frames closer than the minimum spacing.
EXPECTED_FRAME_ERRORS = {"MapillaryOutsideGPXTrackError", "MapillaryDuplicationError"}
# Bearings differ by at most 180 degrees, so this makes direction irrelevant to duplicates
ANY_DIRECTION_DEGREES = 180


class ProcessingError(Exception):
    pass


@dataclass(frozen=True)
class Trim:
    start_seconds: float = 0.0
    end_seconds: float = 0.0


@dataclass(frozen=True)
class FrameOptions:
    sample_interval_seconds: float = 2.0
    trim: Trim = Trim()
    min_spacing_meters: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None


def frames_folder_for(recording: Recording) -> Path:
    return recording.video.parent / f"{recording.video.stem}_frames"


def build_sample_command(
    video: Path, frames_folder: Path, video_start_time: str, sample_interval_seconds: float
) -> list[str]:
    return [
        *MAPILLARY_TOOLS,
        "sample_video",
        str(video),
        str(frames_folder),
        "--rerun",
        "--video_start_time",
        video_start_time,
        # mapillary_tools only honours the time interval once distance sampling is disabled
        "--video_sample_distance",
        "-1",
        "--video_sample_interval",
        str(sample_interval_seconds),
    ]


def trim_window(
    recording_start: datetime.datetime, duration: datetime.timedelta, trim: Trim
) -> tuple[datetime.datetime, datetime.datetime]:
    sampled_start = truncate_to_milliseconds(recording_start)
    keep_from = sampled_start + datetime.timedelta(seconds=trim.start_seconds)
    keep_until = sampled_start + duration - datetime.timedelta(seconds=trim.end_seconds)
    return keep_from, keep_until


def remove_frames_outside(
    frames_folder: Path, keep_from: datetime.datetime, keep_until: datetime.datetime
) -> int:
    output = subprocess.run(
        [
            "exiftool",
            "-json",
            "-recurse",
            "-ext",
            "jpg",
            "-SubSecDateTimeOriginal",
            str(frames_folder),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    frames = json.loads(output)
    if not frames:
        raise ProcessingError(f"No frames sampled in {frames_folder}")
    removed_count = 0
    for frame in frames:
        captured = datetime.datetime.strptime(
            frame["SubSecDateTimeOriginal"], "%Y:%m:%d %H:%M:%S.%f%z"
        )
        if not keep_from <= captured <= keep_until:
            Path(frame["SourceFile"]).unlink()
            removed_count += 1
    if removed_count == len(frames):
        raise ProcessingError(f"Trimming removed every frame in {frames_folder}")
    return removed_count


def build_panorama_tag_command(frames_folder: Path) -> list[str]:
    """Sampled frames lose the video's 360 metadata, so write Google's GPano tags back."""
    return [
        "exiftool",
        "-overwrite_original",
        "-recurse",
        "-ext",
        "jpg",
        "-XMP-GPano:ProjectionType=equirectangular",
        "-XMP-GPano:UsePanoramaViewer=True",
        "-XMP-GPano:FullPanoWidthPixels<ImageWidth",
        "-XMP-GPano:FullPanoHeightPixels<ImageHeight",
        "-XMP-GPano:CroppedAreaImageWidthPixels<ImageWidth",
        "-XMP-GPano:CroppedAreaImageHeightPixels<ImageHeight",
        "-XMP-GPano:CroppedAreaLeftPixels=0",
        "-XMP-GPano:CroppedAreaTopPixels=0",
        str(frames_folder),
    ]


def build_process_command(
    frames_folder: Path,
    track: Path,
    camera_make: str | None = None,
    camera_model: str | None = None,
    min_spacing_meters: float | None = None,
) -> list[str]:
    command = [
        *MAPILLARY_TOOLS,
        "process",
        str(frames_folder),
        "--geotag_source",
        "gpx",
        "--geotag_source_path",
        str(track),
        # Lets the description file record every frame; check_processed_frames decides what fails
        "--skip_process_errors",
    ]
    if camera_make:
        command += ["--device_make", camera_make]
    if camera_model:
        command += ["--device_model", camera_model]
    if min_spacing_meters is not None:
        command += [
            "--duplicate_distance",
            str(min_spacing_meters),
            "--duplicate_angle",
            str(ANY_DIRECTION_DEGREES),
        ]
    return command


def check_processed_frames(description_file: Path) -> int:
    """Fails before upload so a partial sequence never reaches Mapillary."""
    descriptions = json.loads(description_file.read_text(encoding="utf-8"))
    errors = [entry for entry in descriptions if "error" in entry]
    unexpected = [entry for entry in errors if entry["error"]["type"] not in EXPECTED_FRAME_ERRORS]
    if unexpected:
        details = "; ".join(
            f"{Path(entry['filename']).name}: {entry['error']['type']}" for entry in unexpected
        )
        raise ProcessingError(f"Frames failed to process: {details}")

    ready_count = len(descriptions) - len(errors)
    if ready_count == 0:
        raise ProcessingError(
            f"No frame in {description_file.parent} could be placed on the GPX track"
        )
    return ready_count


def build_upload_command(
    frames_folder: Path, user_name: str | None = None, dry_run: bool = False
) -> list[str]:
    command = [*MAPILLARY_TOOLS, "upload", str(frames_folder)]
    if user_name:
        command += ["--user_name", user_name]
    if dry_run:
        command.append("--dry_run")
    return command


def prepare_frames(recording: Recording, frames_folder: Path, options: FrameOptions) -> int:
    recording_start = read_recording_start(recording.video)
    trimming = options.trim != Trim()
    if trimming:
        duration = read_recording_duration(recording.video)
        keep_from, keep_until = trim_window(recording_start, duration, options.trim)
        if keep_from > keep_until:
            raise ProcessingError(
                f"{recording.video.name}: skip_start and skip_end together exceed its "
                f"{duration.total_seconds():g} seconds"
            )
    subprocess.run(
        build_sample_command(
            recording.video,
            frames_folder,
            format_for_mapillary_tools(recording_start),
            options.sample_interval_seconds,
        ),
        check=True,
    )
    if trimming:
        removed_count = remove_frames_outside(frames_folder, keep_from, keep_until)
        print(
            f"Trimmed {removed_count} frames outside "
            f"{keep_from.astimezone(datetime.UTC):%H:%M:%S} to "
            f"{keep_until.astimezone(datetime.UTC):%H:%M:%S} UTC"
        )
    subprocess.run(build_panorama_tag_command(frames_folder), check=True)
    camera_make = options.camera_make or read_camera_make(recording.video)
    subprocess.run(
        build_process_command(
            frames_folder,
            recording.track,
            camera_make,
            options.camera_model,
            options.min_spacing_meters,
        ),
        check=True,
    )
    return check_processed_frames(frames_folder / IMAGE_DESCRIPTION_FILENAME)


def upload_recording(
    recording: Recording,
    options: FrameOptions,
    user_name: str | None = None,
    dry_run: bool = False,
) -> None:
    frames_folder = frames_folder_for(recording)
    ready_count = prepare_frames(recording, frames_folder, options)
    print(f"{ready_count} frames ready for upload")
    subprocess.run(build_upload_command(frames_folder, user_name, dry_run), check=True)
