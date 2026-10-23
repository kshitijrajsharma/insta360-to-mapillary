import datetime
from pathlib import Path
from typing import Any

from mapillary_tools.mp4.mp4_sample_parser import MovieBoxParser, to_datetime


def read_movie_header(video: Path) -> dict[str, Any]:
    return MovieBoxParser.parse_file(video).extract_mvhd_boxdata()


def read_recording_start(video: Path) -> datetime.datetime:
    """Insta360 writes the recording start to creation_time; mapillary_tools reads it as the end."""
    creation_time = read_movie_header(video)["creation_time"]
    if creation_time == 0:
        raise ValueError(f"{video.name} has no creation_time, so it cannot be matched to a GPX")
    return to_datetime(creation_time)


def read_recording_duration(video: Path) -> datetime.timedelta:
    header = read_movie_header(video)
    return datetime.timedelta(seconds=header["duration"] / header["timescale"])


def format_for_mapillary_tools(start: datetime.datetime) -> str:
    utc_start = start.astimezone(datetime.UTC)
    return utc_start.strftime("%Y_%m_%d_%H_%M_%S_") + f"{utc_start.microsecond // 1000:03d}"
