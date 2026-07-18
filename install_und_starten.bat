@echo off
REM ============================================================
REM  Photo Converter - install dependencies and start
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title Photo Converter

echo.
echo === Installing Python dependencies ===
echo.

REM --no-warn-script-location avoids the EXIF.exe warning/abort
python -m pip install --no-warn-script-location --upgrade -r requirements.txt
if errorlevel 1 (
    echo.
    echo [!] pip reported an error.
    echo     If it was only about "EXIF.exe", that is harmless - the packages are installed anyway.
    echo.
)

echo.
echo === Checking ffmpeg ^(for MOV/AVI/MKV -^> MP4^) ===
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [!] ffmpeg not found.
    echo     Videos other than MP4/M4V will be skipped.
    echo     Install: winget install --id Gyan.FFmpeg -e
    echo.
) else (
    echo [OK] ffmpeg found.
)

echo.
echo === Starting the app ===
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [!] The app exited with an error. See the message above.
    pause
)
