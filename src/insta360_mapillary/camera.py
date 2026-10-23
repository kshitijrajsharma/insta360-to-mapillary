import json
import subprocess
from pathlib import Path

INSTA360_STITCHING_SOFTWARE = "Insta360"
INSTA360_MAKE = "Insta360"


def read_camera_make(video: Path) -> str | None:
    """Insta360 Studio exports drop the camera make, but keep Insta360 as the stitching software."""
    output = subprocess.run(
        ["exiftool", "-json", "-XMP-GSpherical:StitchingSoftware", str(video)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    stitching_software = json.loads(output)[0].get("StitchingSoftware")
    if stitching_software == INSTA360_STITCHING_SOFTWARE:
        return INSTA360_MAKE
    return None
