import subprocess
import tempfile
import wave
from pathlib import Path

import requests

from moments import pick_moments


class TranscriptionError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def transcribe(audio, filename, api_key, read_timeout=300, language="sk"):
    try:
        response = requests.post(
            'https://api.openai.com/v1/audio/transcriptions',
            headers={'Authorization': 'Bearer ' + api_key},
            files={'file': (filename, audio, 'audio/wav')},
            data={'model': 'whisper-1', 'response_format': 'verbose_json',
                  'timestamp_granularities[]': 'segment',
                  **({'language': language} if language != 'auto' else {})},
            timeout=(10, read_timeout), allow_redirects=False)
    except requests.RequestException:
        raise TranscriptionError('Spojenie s OpenAI zlyhalo. Skús to znova.', 502) from None
    if response.status_code != 200:
        errors = {401: 'OpenAI odmietlo API kľúč.', 403: 'Kľúč nemá prístup k prepisu.',
                  429: 'OpenAI hlási prekročený limit. Skontroluj kredit alebo skús neskôr.'}
        if response.status_code == 429 and 'insufficient_quota' in response.text:
            errors[429] = 'OpenAI hlási vyčerpaný kredit alebo rozpočet API projektu. Skontroluj fakturáciu na platform.openai.com.'
        raise TranscriptionError(errors.get(response.status_code, 'OpenAI nedokončilo prepis.'),
                                 response.status_code if response.status_code in errors else 502)
    return response.json()["segments"]


def analyze(path, api_key, language="sk"):
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        # Fixed-rate PCM makes each ten-minute part smaller than 20 MB.
        subprocess.run([
            'ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:a:0',
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', '-f', 'segment',
            '-segment_time', '600', '-reset_timestamps', '1',
            str(Path(directory) / '%06d.wav')
        ], check=True, capture_output=True, timeout=900)
        offset = 0.0
        for part in sorted(Path(directory).glob('*.wav')):
            with part.open('rb') as audio:
                segments = transcribe(audio, part.name, api_key, language=language)
            for segment in segments:
                text = segment['text'].strip()
                if text:
                    rows.append(dict(start=round(offset + segment['start'], 3),
                                     end=round(offset + segment['end'], 3), text=text))
            with wave.open(str(part), 'rb') as wav:
                offset += wav.getnframes() / wav.getframerate()
    return summarize(rows)


def summarize(rows: list) -> dict:
    return dict(captions=rows, moments=pick_moments(rows))
