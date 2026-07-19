"""The actual work steps: reading dates, building target paths and converting
each media file. This module is GUI-free and can be tested on its own.
"""

import os
import re
import stat
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from collections import namedtuple

from .constants import (RAW_EXTENSIONS, HEIC_EXTENSIONS, JPG_EXTENSIONS,
                        MP4_EXTENSIONS, VIDEO_CONV_EXTENSIONS)

# Enable HEIF/AVIF support in Pillow module-wide (best-effort) so image
# conversion works on HEIC files without extra setup by the caller.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

# Silence exifread's noisy "File format not recognized." messages on stderr;
# we report a missing capture date per file in our own log instead.
logging.getLogger('exifread').setLevel(logging.CRITICAL)


# --- Step 1: inspect the source file -----------------------------------------

def is_online_only(filepath: Path) -> bool:
    """True if the file is an iCloud/OneDrive placeholder whose content is not
    stored locally yet. Reads only file attributes (no data access), so it does
    NOT trigger a slow download. Lets us skip such files instead of hanging on
    them for ~2 minutes while the cloud provider tries to fetch them.
    """
    try:
        attrs = os.stat(filepath).st_file_attributes
    except (AttributeError, OSError):
        return False  # attribute unavailable (e.g. non-Windows) -> don't skip
    offline = getattr(stat, 'FILE_ATTRIBUTE_OFFLINE', 0x1000)
    recall  = getattr(stat, 'FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS', 0x400000)
    return bool(attrs & (offline | recall))


# Date patterns found in common file names (WhatsApp, Screenshot, Pixel, Signal,
# IMG_/VID_ with a date, ...). Most specific first.
_DATE_TIME_PATTERNS = [
    # 2026-03-01 [ at / _ / - / T ] 17.33.42  (WhatsApp, Signal, Screenshot)
    re.compile(r'(20\d{2})[-_.](\d{2})[-_.](\d{2})[^\d]{1,5}(\d{2})[.\-:_ ](\d{2})[.\-:_ ](\d{2})'),
    # 20260301 [ _ / - / T ] 173342 (optional trailing ms)  (PXL_, IMG_, VID_)
    re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})[^\d]{1,3}(\d{2})(\d{2})(\d{2})'),
]
_DATE_ONLY_PATTERNS = [
    re.compile(r'(20\d{2})[-_.](\d{2})[-_.](\d{2})'),         # 2026-03-01
    re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)'),      # 20260301
]


def date_from_filename(name: str):
    """Tries to parse a capture date/time out of a file name. Returns a datetime
    or None. Used as a fallback when a file has no EXIF date."""
    for pat in _DATE_TIME_PATTERNS:
        m = pat.search(name)
        if m:
            y, mo, d, h, mi, s = (int(x) for x in m.groups())
            try:
                return datetime(y, mo, d, h, mi, s)
            except ValueError:
                pass
    for pat in _DATE_ONLY_PATTERNS:
        m = pat.search(name)
        if m:
            y, mo, d = (int(x) for x in m.groups())
            try:
                return datetime(y, mo, d, 12, 0, 0)  # noon: time unknown
            except ValueError:
                pass
    return None


def get_exif_date(filepath: Path):
    """Determines the capture date. Returns (date, source) where source is:
      'exif'     - read from EXIF metadata
      'filename' - parsed from the file name (no EXIF date present)
      'file'     - fell back to the file's modified time
    """
    try:
        import exifread
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal', details=False)
        for tag in ('EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime'):
            if tag in tags:
                return datetime.strptime(str(tags[tag]), '%Y:%m:%d %H:%M:%S'), 'exif'
    except Exception:
        pass
    # Fallback 1: a date embedded in the file name
    from_name = date_from_filename(filepath.name)
    if from_name is not None:
        return from_name, 'filename'
    # Fallback 2: file modified time
    return datetime.fromtimestamp(filepath.stat().st_mtime), 'file'


# --- Step 2: decide the destination path -------------------------------------

def build_output_path(base: Path, date: datetime, structure: str, stem: str, ext: str,
                      skip_existing: bool = False):
    """Returns the target path based on folder structure and date.

    If skip_existing is True and the target file already exists, returns None
    to signal that the file should be skipped (idempotent re-runs). Otherwise a
    non-colliding name (stem_1, stem_2, ...) is chosen so nothing is overwritten.
    """
    if structure == 'Year':
        folder = base / str(date.year)
    elif structure == 'Year/Month':
        folder = base / str(date.year) / f"{date.year}-{date.month:02d}"
    else:  # Year/Month/Day
        folder = base / str(date.year) / f"{date.year}-{date.month:02d}" / f"{date.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / (stem + ext)
    if candidate.exists():
        if skip_existing:
            return None
        counter = 1
        while candidate.exists():
            candidate = folder / f"{stem}_{counter}{ext}"
            counter += 1
    return candidate


def set_file_date(filepath: Path, date: datetime):
    """Sets the file timestamp to the capture date."""
    ts = date.timestamp()
    os.utime(filepath, (ts, ts))


# --- Step 3: convert / copy the media ----------------------------------------

def convert_raw_to_jpg(src: Path, dst: Path):
    """Converts RAW (NEF, RAF, ...) to JPG via rawpy + Pillow.

    Some files in the iCloud library carry a RAW extension (.nef/.raf) but
    actually contain a JPEG/HEIC (iCloud proxy). In that case libraw cannot read
    them -> we fall back to Pillow instead of discarding the file as an error.
    """
    import rawpy
    from PIL import Image
    try:
        with rawpy.imread(str(src)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
        Image.fromarray(rgb).save(str(dst), 'JPEG', quality=92)
    except rawpy.LibRawError:
        convert_image_to_jpg(src, dst)


def convert_image_to_jpg(src: Path, dst: Path):
    """Converts HEIC/PNG/TIFF/... to JPG via Pillow."""
    from PIL import Image
    with Image.open(str(src)) as img:
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        img.save(str(dst), 'JPEG', quality=92)


def copy_exif_to_jpg(src: Path, dst: Path):
    """Copies EXIF data into the JPG file (best-effort)."""
    try:
        import piexif
        piexif.insert(piexif.dump(piexif.load(str(src))), str(dst))
    except Exception:
        pass


def ffmpeg_available() -> bool:
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _ffmpeg_error(stderr: str) -> str:
    """Extracts the most meaningful line from ffmpeg's stderr for the log.

    ffmpeg prints its version banner and build flags first, so the raw tail is
    noisy. We pick the last line that looks like an actual error message.
    """
    lines = [ln.strip() for ln in (stderr or '').splitlines() if ln.strip()]
    keywords = ('error', 'invalid', 'could not', 'no such', 'unable',
                'failed', 'permission', 'not contain', 'moov atom')
    for ln in reversed(lines):
        if any(k in ln.lower() for k in keywords):
            return ln
    return lines[-1] if lines else 'ffmpeg failed with no output'


def convert_video_to_mp4(src: Path, dst: Path):
    """Converts a video to MP4 via ffmpeg. Raises RuntimeError with a clean,
    single-line message if ffmpeg fails."""
    result = subprocess.run(
        ['ffmpeg', '-i', str(src), '-c:v', 'libx264', '-c:a', 'aac',
         '-movflags', '+faststart', '-y', str(dst)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(_ffmpeg_error(result.stderr))


# --- Step 4: process one file end-to-end (GUI-independent) --------------------

# category:  'ok' | 'exists' | 'online' | 'noffmpeg' | 'broken' | 'error'
# tag:       log colour tag ('ok' | 'warn' | 'info' | 'err')
# no_date:   True if the date fell back to the file timestamp (no EXIF, no name)
# from_name: True if the date was parsed from the file name
Outcome = namedtuple('Outcome', 'category message tag no_date from_name',
                     defaults=(False, False))


def process_file(fp: Path, dst: Path, structure: str, skip_existing: bool,
                 skip_online: bool, lower_ext: bool, ffmpeg_ok: bool) -> Outcome:
    """Convert/copy a single file and return an Outcome describing what happened.

    Never raises: any failure is returned as an 'error' Outcome so the caller can
    keep going through the rest of the files.
    """
    ext = fp.suffix.lower()

    # Skip iCloud placeholders quickly (before any read that would hang for
    # ~2 minutes while the cloud provider tries to download them).
    if skip_online and is_online_only(fp):
        return Outcome('online', f'SKIP (not downloaded)  {fp.name}', 'warn', False)

    try:
        # Empty / dataless file -> nothing to convert, skip cleanly
        try:
            if fp.stat().st_size == 0:
                return Outcome('broken', f'SKIP (empty file)  {fp.name}', 'warn', False)
        except OSError:
            pass

        # Non-MP4 video without ffmpeg cannot be converted -> skip
        if ext in VIDEO_CONV_EXTENSIONS and not ffmpeg_ok:
            return Outcome('noffmpeg', f'SKIP (no ffmpeg)  {fp.name}', 'info', False)

        date, datesrc = get_exif_date(fp)

        is_video = ext in MP4_EXTENSIONS or ext in VIDEO_CONV_EXTENSIONS
        base_ext = '.mp4' if is_video else '.jpg'
        if not lower_ext:
            base_ext = base_ext.upper()

        out = build_output_path(dst, date, structure, fp.stem, base_ext, skip_existing)
        if out is None:
            return Outcome('exists', f'SKIP (exists)  {fp.name}', 'info', False)

        if ext in MP4_EXTENSIONS:                 # MP4/M4V -> copy
            shutil.copy2(fp, out); kind = ''
        elif ext in VIDEO_CONV_EXTENSIONS:        # MOV/AVI/... -> MP4
            try:
                convert_video_to_mp4(fp, out)
            except Exception as e:
                # broken/unreadable source video -> skip cleanly, not a hard error
                try:
                    out.unlink(missing_ok=True)  # remove any partial output
                except OSError:
                    pass
                return Outcome('broken', f'SKIP (broken video)  {fp.name}:  {e}', 'warn', False)
            kind = '  [->MP4]'
        elif ext in JPG_EXTENSIONS:               # JPG -> copy
            shutil.copy2(fp, out); kind = ''
        elif ext in RAW_EXTENSIONS:               # RAW -> JPG
            convert_raw_to_jpg(fp, out); copy_exif_to_jpg(fp, out); kind = '  [RAW->JPG]'
        else:                                     # HEIC/PNG/... -> JPG
            convert_image_to_jpg(fp, out); copy_exif_to_jpg(fp, out); kind = '  [->JPG]'

        set_file_date(out, date)
        stamp = date.strftime('%Y-%m-%d %H:%M:%S')
        if datesrc == 'exif':
            note, tag = '', 'ok'
        elif datesrc == 'filename':
            note, tag = '   [date from filename]', 'ok'
        else:  # 'file'
            note, tag = '   [no EXIF date -> file date]', 'warn'
        msg = f'OK  {fp.name}  ->  {out.relative_to(dst)}   {stamp}{kind}{note}'
        return Outcome('ok', msg, tag,
                       no_date=(datesrc == 'file'), from_name=(datesrc == 'filename'))

    except OSError as e:
        # Unreadable source: almost always an iCloud/OneDrive placeholder that
        # is not downloaded locally ([Errno 22] when the provider can't fetch it).
        if is_online_only(fp):
            return Outcome('online', f'SKIP (not downloaded)  {fp.name}', 'warn')
        return Outcome('broken', f'SKIP (unreadable file)  {fp.name}:  {e}', 'warn')
    except Exception as e:
        return Outcome('error', f'ERROR  {fp.name}:  {e}', 'err')
