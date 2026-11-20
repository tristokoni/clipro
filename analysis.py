import subprocess
import tempfile
import wave
from pathlib import Path

import requests


class TranscriptionError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def analyze(path, api_key):
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        # Fixed-rate PCM makes each ten-minute part smaller than 20 MB.
        subprocess.run([
            'ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:a:0',
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', '-f', 'segment',
            '-segment_time', '600', '-reset_timestamps', '1',
            str(Path(directory) / '%06d.wav')
        ], check=True, capture_output=True)
        offset = 0.0
        for part in sorted(Path(directory).glob('*.wav')):
            with part.open('rb') as audio:
                try:
                    response = requests.post(
                        'https://api.openai.com/v1/audio/transcriptions',
                        headers={'Authorization': 'Bearer ' + api_key},
                        files={'file': (part.name, audio, 'audio/wav')},
                        data={'model': 'whisper-1', 'response_format': 'verbose_json',
                              'timestamp_granularities[]': 'segment'},
                        timeout=(10, 300), allow_redirects=False)
                except requests.RequestException:
                    raise TranscriptionError('Spojenie s OpenAI zlyhalo. Skús to znova.', 502) from None
            if response.status_code != 200:
                errors = {401: 'OpenAI odmietlo API kľúč.', 403: 'Kľúč nemá prístup k prepisu.',
                          429: 'OpenAI hlási prekročený limit. Skontroluj kredit alebo skús neskôr.'}
                raise TranscriptionError(errors.get(response.status_code, 'OpenAI nedokončilo prepis.'),
                                         response.status_code if response.status_code in errors else 502)
            for segment in response.json()['segments']:
                text = segment['text'].strip()
                if text:
                    rows.append(dict(start=round(offset + segment['start'], 3),
                                     end=round(offset + segment['end'], 3), text=text))
            with wave.open(str(part), 'rb') as wav:
                offset += wav.getnframes() / wav.getframerate()
    # Prefer dense speech and questions. Keep suggestions distinct in time.
    ranked = sorted(rows, key=lambda r: (int("?" in r["text"]), len(r["text"].split()) / max(1, r["end"]-r["start"])), reverse=True)
    moments = []
    for row in ranked:
        if all(abs(row["start"] - other["start"]) >= 25 for other in moments):
            moments.append(row)
        if len(moments) == 5:
            break
    return dict(captions=rows, moments=moments)
