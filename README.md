# insta360-mapillary

Uploads 360 video from an Insta360 camera to [Mapillary](https://www.mapillary.com), using the GPX track that Insta360 Studio exports next to each video.

For every `NAME.mp4` in a folder with a matching `NAME.gpx`, the tool extracts an image every few seconds with [mapillary_tools](https://github.com/mapillary/mapillary_tools), tags it as a 360 panorama, places it on the track by time, and uploads the sequence. Image times count from the video's `creation_time`. On an X6 export from Insta360 Studio this is the start of the recording, while mapillary_tools reads it as the end ([`ffmpeg.py`](https://github.com/mapillary/mapillary_tools/blob/v0.14.7/mapillary_tools/ffmpeg.py#L598-L631)), so the tool passes it as the start time.

Images outside the track or too close to the previous image are skipped. Any other error stops the run before that video is uploaded. Videos earlier in the folder are already uploaded by then.

## Requirements

- Python 3.11 or newer
- `ffmpeg`, `ffprobe` and `exiftool`. H.265 exports need an HEVC decoder, which Fedora's default `ffmpeg-free` leaves out (checked on Fedora 43). Use the full `ffmpeg` from [RPM Fusion](https://rpmfusion.org/Howto/Multimedia).

## Installation

```bash
uv tool install insta360-mapillary --with-executables-from mapillary-tools
mapillary_tools authenticate --user_name YOUR_MAPILLARY_USERNAME
```

## Usage

Record with GPS turned on in the Insta360 app, then export each clip from Insta360 Studio as MP4 with **Export GPX file** ticked.

```bash
insta360-mapillary ~/mapillary/ride1
```

| Option | Default | Description |
| --- | --- | --- |
| `--user-name` | | Mapillary account, when more than one is logged in |
| `--sample-interval` | `2` | Seconds between extracted images |
| `--skip-start` | `0` | Seconds left out at the start of each video |
| `--skip-end` | `0` | Seconds left out at the end of each video |
| `--min-spacing` | | Keep an image only when it is more than this many metres from the previous kept image, in any direction |
| `--camera-make` | `Insta360` for Studio exports | Camera make recorded on Mapillary |
| `--camera-model` | | Camera model recorded on Mapillary, such as `X6` |
| `--dry-run`, `--no-dry-run` | off | Process everything and write the upload to a local folder |

Options can also be set in a YAML file passed with `--config`, using the option names with underscores. A relative `folder` counts from the file's folder. `recordings` sets `skip_start` and `skip_end` per video, keyed by file name without extension, and these take precedence over the file's own values. Command-line values take precedence over everything in the file.

```yaml
folder: ~/mapillary/ride1
camera_model: X6
skip_start: 10
recordings:
  street:
    skip_start: 114
    skip_end: 6
```

Extracted images are written to `NAME_frames/NAME.mp4/` next to each video and are replaced on every run.

## Development

Development uses [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just):

```bash
just setup
just lint
just test
```
