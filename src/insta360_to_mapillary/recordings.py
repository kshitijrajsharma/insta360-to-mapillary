from dataclasses import dataclass
from pathlib import Path


class MissingTrackError(Exception):
    pass


@dataclass(frozen=True)
class Recording:
    video: Path
    track: Path


def find_recordings(folder: Path) -> list[Recording]:
    """Insta360 Studio writes each GPX next to its video under the same name."""
    videos = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".mp4")
    if not videos:
        raise FileNotFoundError(f"No .mp4 files in {folder}")

    videos_without_track = [
        video.name for video in videos if not video.with_suffix(".gpx").is_file()
    ]
    if videos_without_track:
        raise MissingTrackError(
            f"No matching .gpx for: {', '.join(videos_without_track)}. "
            "Export from Insta360 Studio with 'Export GPX File' ticked."
        )
    return [Recording(video=video, track=video.with_suffix(".gpx")) for video in videos]
