# Guide

From recording a ride with an Insta360 camera to seeing it on Mapillary.

## 1. Install and log in

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then install the tool and log in to Mapillary.

```bash
uv tool install insta360-to-mapillary --with-executables-from mapillary-tools
mapillary_tools authenticate --user_name YOUR_MAPILLARY_USERNAME
```

## 2. Set up the camera

1. Turn on the camera and connect it to the Insta360 app on your phone.
2. Choose a video mode. Use the highest resolution, or HD at 60 fps to save space.
3. Turn on the GPS switch on the app's shooting page. The camera has no GPS of its own and records the phone's location ([Insta360 manual](https://onlinemanual.insta360.com/x5/en-us/operating_tutorials/clips/gps)).

## 3. Record

Start recording from the Insta360 app, so the video and the GPS log start together.

A second GPX track from another app, such as the [OsmAnd](https://osmand.net) trip recorder, is optional. If you use one, name it after the video (`NAME.gpx`) and use it in place of the one Insta360 Studio exports.

## 4. Export

1. Connect the camera to your computer with a USB-C cable.
2. Open Insta360 Studio and export each clip as MP4 with **Export GPX File** ticked.

Each clip gives one `NAME.mp4` and one `NAME.gpx` in the same folder.

## 5. Upload

```bash
insta360-to-mapillary ~/mapillary/ride1
```

Or put the options in a YAML file and pass it with `--config`. See the [README](README.md#usage) for all options. Add `--dry-run` to check everything before a real upload.

## 6. Check Mapillary

The sequence appears on your Mapillary profile after Mapillary has processed it.
