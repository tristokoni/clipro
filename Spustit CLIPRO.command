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
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
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
exec .venv/bin/python launch_mac.py
