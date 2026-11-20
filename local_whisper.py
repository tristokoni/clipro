"""Offline inference with whisper.cpp. The first run fetches the multilingual small model."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Lock

import requests

from moments import cue_groups
from analysis import TranscriptionError, summarize

MODEL_URL = ("https://huggingface.co/ggerganov/whisper.cpp/resolve/"
             "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-small-q5_1.bin?download=true")
MODEL_SHA256 = "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"
MODEL_SIZE = 190085487
model_lock = Lock()


def model_file() -> Path:
    custom = os.getenv("CLIPRO_WHISPER_MODEL")
    if custom:
        path = Path(custom).expanduser()
        if not path.is_file():
            raise TranscriptionError("Skontroluj cestu CLIPRO_WHISPER_MODEL.", 503)
        return path
    cache = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "clipro"
    path = cache / "ggml-small-q5_1.bin"
    if path.is_file() and path.stat().st_size == MODEL_SIZE:
        return path
    cache.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=cache, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        digest = hashlib.sha256()
        with requests.get(MODEL_URL, stream=True, timeout=(10, 60)) as response, temporary.open("wb") as out:
            response.raise_for_status()
            for chunk in response.iter_content(1024 * 1024):
                out.write(chunk)
                digest.update(chunk)
                if out.tell() > MODEL_SIZE:
                    break
        if digest.hexdigest() != MODEL_SHA256:
            raise TranscriptionError("Model sa nestiahol celý. Skús prepis znova.", 503)
        temporary.replace(path)
    except requests.RequestException:
        raise TranscriptionError("Prvé stiahnutie modelu potrebuje internet. Skontroluj pripojenie a skús znova.", 503) from None
    finally:
        temporary.unlink(missing_ok=True)
    return path


def analyze_local(source: Path, duration: float, language: str = "sk", progress=None) -> dict:
    cli = shutil.which("whisper-cli")
    if not cli:
        raise TranscriptionError("Chýba whisper-cli. Na Macu otvor Spustit CLIPRO.command alebo použi brew install whisper.cpp.", 503)
    if not model_lock.acquire(blocking=False):
        raise TranscriptionError("Na tomto počítači už beží lokálny prepis.", 409)
    try:
        model = model_file()
        rows = []
        with TemporaryDirectory() as temp:
            total = max(1, math.ceil(duration / 600))
            for part in range(total):
                offset = part * 600
                if progress:
                    progress(part + 1, total)
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(offset),
                                "-i", str(source), "-t", "600", "-map", "0:a:0", "-ar", "16000",
                                "-ac", "1", "-c:a", "pcm_s16le", "audio.wav"], cwd=temp,
                               check=True, capture_output=True, timeout=180)
                subprocess.run([cli, "-m", str(model.resolve()), "-f", "audio.wav", "-l", language,
                                "-oj", "-of", "result", "-ml", "1", "-sow"], cwd=temp,
                               check=True, capture_output=True, timeout=1800)
                result = json.loads((Path(temp) / "result.json").read_text(encoding="utf-8"))
                for segment in result["transcription"]:
                    text = segment["text"].strip()
                    start = offset + segment["offsets"]["from"] / 1000
                    end = min(duration, offset + segment["offsets"]["to"] / 1000)
                    if text and end > start:
                        rows.append(dict(start=start, end=end, text=text))
        return summarize(cue_groups(rows))
    except subprocess.TimeoutExpired:
        raise TranscriptionError("Lokálny prepis prekročil časový limit.", 504) from None
    except subprocess.CalledProcessError:
        raise TranscriptionError("Prepis zlyhal. Skontroluj zvukovú stopu, whisper-cli a dostupnú pamäť.", 422) from None
    finally:
        model_lock.release()
