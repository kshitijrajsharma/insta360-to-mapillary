import argparse
import importlib.metadata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import yaml

from insta360_to_mapillary.config import (
    TRIM_KEYS,
    ConfigError,
    check_non_negative,
    check_positive,
    check_text,
    load_config,
)
from insta360_to_mapillary.recordings import MissingTrackError, find_recordings
from insta360_to_mapillary.upload import (
    DEFAULT_CAMERA_MAKE,
    FrameOptions,
    Trim,
    upload_recording,
)

DEFAULTS: dict[str, Any] = {
    "sample_interval": 2.0,
    "skip_start": 0.0,
    "skip_end": 0.0,
    "dry_run": False,
    "camera_make": DEFAULT_CAMERA_MAKE,
}


@dataclass(frozen=True)
class RunOptions:
    folder: Path
    sample_interval: float
    skip_start: float
    skip_end: float
    dry_run: bool
    camera_make: str
    min_spacing: float | None = None
    camera_model: str | None = None
    user_name: str | None = None
    # Per-video skip_start and skip_end from the config file, by video name without extension
    recording_trims: dict[str, dict[str, float]] = field(default_factory=dict)

    def frame_options_for(self, video_stem: str) -> FrameOptions:
        trims = self.recording_trims.get(video_stem, {})
        return FrameOptions(
            sample_interval_seconds=self.sample_interval,
            trim=Trim(
                start_seconds=trims.get("skip_start", self.skip_start),
                end_seconds=trims.get("skip_end", self.skip_end),
            ),
            min_spacing_meters=self.min_spacing,
            camera_make=self.camera_make,
            camera_model=self.camera_model,
        )


ParsedValue = TypeVar("ParsedValue")


def argument_type(
    convert: Callable[[str], ParsedValue], check: Callable[[ParsedValue], ParsedValue]
) -> Callable[[str], ParsedValue]:
    def parse(value: str) -> ParsedValue:
        try:
            return check(convert(value))
        except ValueError as error:
            raise argparse.ArgumentTypeError(str(error)) from error

    return parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="insta360-to-mapillary",
        description="Upload every MP4 + GPX pair exported from Insta360 Studio to Mapillary.",
    )
    parser.add_argument(
        "folder", type=Path, nargs="?", help="Folder with the exported .mp4 and .gpx files"
    )
    parser.add_argument("--config", type=Path, help="YAML file with any of these options")
    parser.add_argument(
        "--user-name", type=argument_type(str, check_text), help="Mapillary account to upload to"
    )
    parser.add_argument(
        "--sample-interval",
        type=argument_type(float, check_positive),
        help=f"Seconds between extracted images (default: {DEFAULTS['sample_interval']:g})",
    )
    parser.add_argument(
        "--skip-start",
        type=argument_type(float, check_non_negative),
        help=f"Seconds left out at each video's start (default: {DEFAULTS['skip_start']:g})",
    )
    parser.add_argument(
        "--skip-end",
        type=argument_type(float, check_non_negative),
        help=f"Seconds left out at each video's end (default: {DEFAULTS['skip_end']:g})",
    )
    parser.add_argument(
        "--min-spacing",
        type=argument_type(float, check_positive),
        help="Keep an image only when it is more than this many metres from the previous kept "
        "image, in any direction",
    )
    parser.add_argument(
        "--camera-make",
        type=argument_type(str, check_text),
        help=f"Camera make recorded on Mapillary (default: {DEFAULTS['camera_make']})",
    )
    parser.add_argument(
        "--camera-model",
        type=argument_type(str, check_text),
        help="Camera model recorded on Mapillary, such as X6",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Process everything and write the upload to a local folder",
    )
    parser.add_argument(
        "--version", action="version", version=importlib.metadata.version("insta360-to-mapillary")
    )
    return parser


def read_config(parser: argparse.ArgumentParser, path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        return load_config(path)
    except (ConfigError, OSError, yaml.YAMLError) as error:
        parser.error(str(error))


def recording_trims_without(
    recordings: dict[str, dict[str, float]], command_line: dict[str, Any]
) -> dict[str, dict[str, float]]:
    """A trim given on the command line applies to every video, per-video trims included."""
    overridden = {key for key in TRIM_KEYS if command_line[key] is not None}
    return {
        name: {key: value for key, value in trims.items() if key not in overridden}
        for name, trims in recordings.items()
    }


def resolve_options(arguments: list[str] | None = None) -> RunOptions:
    """Command-line values override the config file, which overrides the defaults."""
    parser = build_parser()
    command_line = vars(parser.parse_args(arguments))
    config = read_config(parser, command_line.pop("config"))
    merged = DEFAULTS | config
    merged |= {key: value for key, value in command_line.items() if value is not None}
    if "folder" not in merged:
        parser.error("give a folder, or set folder in the config file")
    merged["folder"] = merged["folder"].expanduser()
    merged["recording_trims"] = recording_trims_without(merged.pop("recordings", {}), command_line)
    return RunOptions(**merged)


def main(arguments: list[str] | None = None) -> None:
    options = resolve_options(arguments)
    try:
        recordings = find_recordings(options.folder)
    except (OSError, MissingTrackError) as error:
        raise SystemExit(str(error)) from error
    unknown = sorted(
        set(options.recording_trims) - {recording.video.stem for recording in recordings}
    )
    if unknown:
        raise SystemExit(f"recordings lists videos not in {options.folder}: {unknown}")
    for recording in recordings:
        print(f"Uploading {recording.video.name} with {recording.track.name}")
        upload_recording(
            recording,
            options.frame_options_for(recording.video.stem),
            user_name=options.user_name,
            dry_run=options.dry_run,
        )
