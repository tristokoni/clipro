#!/bin/bash
set -eu
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  if ! command -v brew >/dev/null; then
    echo "CLIPRO potrebuje FFmpeg. Nainštaluj Homebrew z https://brew.sh a znova otvor tento súbor."
    exit 1
  fi
  echo "Inštalujem FFmpeg cez Homebrew…"
  brew install ffmpeg
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  if ! command -v brew >/dev/null; then
    echo "Nainštaluj Python 3 z https://www.python.org/downloads/macos/ a znova otvor tento súbor."
    exit 1
  fi
  brew install python
  hash -r
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import flask, requests, keyring' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
# Prefer the downloader and its matching YouTube components from this installation.
if .venv/bin/python -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  if ! .venv/bin/python -c 'import yt_dlp_ejs; from yt_dlp.version import __version__; assert tuple(map(int, __version__.split(".")[:3])) >= (2026, 10, 26)' 2>/dev/null; then
    .venv/bin/python -m pip install --upgrade 'yt-dlp[default]>=2026.10.26' || echo "Inštalácia lokálneho yt-dlp zlyhala."
  fi
fi
export PATH="$PWD/.venv/bin:$PATH"
if ! command -v yt-dlp >/dev/null && command -v brew >/dev/null; then
  brew install yt-dlp || echo "Inštalácia yt-dlp zlyhala."
fi
if ! command -v whisper-cli >/dev/null && command -v brew >/dev/null; then
  brew install whisper-cpp || echo "Pre lokálny prepis treba whisper-cpp."
fi
if ! command -v deno >/dev/null && command -v brew >/dev/null; then
  brew install deno || echo "Inštalácia Deno pre import z YouTube zlyhala."
fi
exec .venv/bin/python launch_mac.py
