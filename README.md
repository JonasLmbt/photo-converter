# Photo Converter

A small Windows desktop tool (tkinter GUI) that converts photos and videos from
an iCloud Photos library into JPG/MP4 and sorts them into date-based folders.

- **RAW** (NEF, RAF, DNG, CR2, …) → JPG via `rawpy`/libraw
- **HEIC / HEIF / AVIF** → JPG via `pillow-heif`
- **PNG / TIFF / BMP / WEBP** → JPG via Pillow
- **JPG** → copied as-is
- **MP4 / M4V** → copied as-is
- **MOV / AVI / MKV / …** → MP4 via ffmpeg

The capture date is read from EXIF (`DateTimeOriginal`) and applied both to the
target folder (`Year/Month`, etc.) and the file timestamp. If a file has no EXIF
date, the file's modified time is used instead (flagged in the log).

## Requirements

- Python 3.9+
- `pip install -r requirements.txt` (rawpy, Pillow, pillow-heif, piexif, exifread)
- **ffmpeg** on PATH — only needed for non-MP4 videos
  (`winget install --id Gyan.FFmpeg -e`)

## Run

```
python main.py
```

On Windows you can also double-click **`install_und_starten.bat`**, which installs
the dependencies first and then launches the app. The `.bat` is only a
convenience wrapper — once the packages are installed, `python main.py` is enough.

## Project layout

```
main.py                     Entry point (starts the GUI)
photo_converter/
    constants.py            Supported file types and GUI theme
    conversion.py           The work steps: dates, paths, conversions, process_file()
    gui.py                  Tkinter window, options and logging
install_und_starten.bat     Windows helper: install deps + start
requirements.txt
```

`conversion.py` is GUI-free, so the conversion logic can be imported and tested
without opening a window.

## Options in the app

- **Skip files that already exist** — makes re-runs idempotent (no duplicates).
- **Skip files not downloaded from iCloud** — online-only placeholders are skipped
  instantly instead of hanging while the cloud provider tries to download them.
- **Lowercase extensions (.jpg)** — toggle `.jpg` vs `.JPG` in the output.
- **Save log** — export the run log to a `.txt` file.

## Notes

- Some `.NEF`/`.RAF` files in an iCloud library are actually JPEGs (iCloud
  proxies). libraw can't read those, so the app falls back to Pillow.
- To convert online-only RAW files, first download them in Explorer
  ("Always keep on this device"), then run again.
