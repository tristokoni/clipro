"""Offline inference with whisper.cpp. The first run fetches the multilingual tiny model."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Lock

import requests

from analysis import TranscriptionError, summarize

MODEL_URL = ("https://huggingface.co/ggerganov/whisper.cpp/resolve/"
             "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-tiny.bin?download=true")
MODEL_SHA256 = "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21"
MODEL_SIZE = 77691713
model_lock = Lock()


def model_file() -> Path:
    custom = os.getenv("CLIPRO_WHISPER_MODEL")
    if custom:
        path = Path(custom).expanduser()
        if not path.is_file():
            raise TranscriptionError("Skontroluj cestu CLIPRO_WHISPER_MODEL.", 503)
        return path
    cache = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "clipro"
    path = cache / "ggml-tiny.bin"
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


def analyze_local(source: Path, duration: float) -> dict:
    cli = shutil.which("whisper-cli")
    if not cli:
        raise TranscriptionError("Chýba whisper-cli. Na Macu otvor Spustit CLIPRO.command alebo použi brew install whisper-cpp.", 503)
    if not model_lock.acquire(blocking=False):
        raise TranscriptionError("Na tomto počítači už beží lokálny prepis.", 409)
    try:
        model = model_file()
        rows = []
        with TemporaryDirectory() as temp:
            for offset in range(0, max(1, int(duration + .999)), 600):
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(offset),
                                "-i", str(source), "-t", "600", "-map", "0:a:0", "-ar", "16000",
                                "-ac", "1", "-c:a", "pcm_s16le", "audio.wav"], cwd=temp,
                               check=True, capture_output=True, timeout=180)
                subprocess.run([cli, "-m", str(model.resolve()), "-f", "audio.wav", "-l", "auto",
                                "-oj", "-of", "result", "-ml", "62", "-sow"], cwd=temp,
                               check=True, capture_output=True, timeout=1800)
                result = json.loads((Path(temp) / "result.json").read_text(encoding="utf-8"))
                for segment in result["transcription"]:
                    text = segment["text"].strip()
                    start = offset + segment["offsets"]["from"] / 1000
                    end = min(duration, offset + segment["offsets"]["to"] / 1000)
                    if text and end > start:
                        rows.append(dict(start=start, end=end, text=text))
        return summarize(rows)
    except subprocess.TimeoutExpired:
        raise TranscriptionError("Lokálny prepis prekročil časový limit.", 504) from None
    except subprocess.CalledProcessError:
        raise TranscriptionError("Prepis zlyhal. Skontroluj zvukovú stopu, whisper-cli a dostupnú pamäť.", 422) from None
    finally:
        model_lock.release()
