import datetime
import json
import subprocess
from pathlib import Path
from typing import Any


def probe_video_stream(video: Path) -> dict[str, Any]:
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=duration:stream_tags=creation_time",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(probe.stdout)["streams"][0]


def read_recording_start(video: Path) -> datetime.datetime:
    """Insta360 writes the recording start to creation_time; mapillary_tools reads it as the end."""
    tags = probe_video_stream(video).get("tags", {})
    if "creation_time" not in tags:
        raise ValueError(f"{video.name} has no creation_time, so it cannot be matched to a GPX")
    start = datetime.datetime.fromisoformat(tags["creation_time"])
    if start.tzinfo is None:
        raise ValueError(f"{video.name} creation_time has no timezone: {tags['creation_time']}")
    return start


def read_recording_duration(video: Path) -> datetime.timedelta:
    stream = probe_video_stream(video)
    if "duration" not in stream:
        raise ValueError(f"{video.name} has no video stream duration")
    return datetime.timedelta(seconds=float(stream["duration"]))


def truncate_to_milliseconds(moment: datetime.datetime) -> datetime.datetime:
    """mapillary_tools takes the start time in milliseconds, so frame times count from this."""
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


def format_for_mapillary_tools(start: datetime.datetime) -> str:
    utc_start = start.astimezone(datetime.UTC)
    return utc_start.strftime("%Y_%m_%d_%H_%M_%S_") + f"{utc_start.microsecond // 1000:03d}"
