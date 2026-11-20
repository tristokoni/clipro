# CLIPRO — video clipping dashboard

Lokálna webová aplikácia na upload videí, výber momentov a export vertikálnych klipov (1080×1920). Skutočný export zabezpečuje FFmpeg, nie demo dáta.

## Spustenie (macOS / Windows / Linux)

1. Nainštaluj Python 3.10+ a FFmpeg (`brew install ffmpeg` na macOS, `winget install Gyan.FFmpeg` na Windows).
2. V priečinku projektu spusti:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

3. Otvor http://127.0.0.1:5050

## Čo funguje
- Upload vlastných MP4/MOV/MKV/WEBM/M4V súborov (max 2 GB)
- Video prehrávač, označenie začiatku/konca, 3 vertikálne rozloženia
- Serverový export MP4 (H.264/AAC) a stiahnutie
- Lokálna knižnica projektov a klipov, vymazanie
- Dashboard so skutočnými počtami

## Čo je pripravené pre ďalšiu fázu
- Trend Radar / živé streamy: potrebujú integrácie YouTube/Twitch API a autorizáciu
- AI detekcia momentov / titulky: potrebujú transcription backend (napr. faster-whisper)
- Zverejňovanie na sociálne siete: potrebuje schválené API a prihlásenie
- Hook je uložený ako textové metadáta, nie je zatiaľ vložený do obrazu

Nie je hostované verejne; ide o lokálnu MVP aplikáciu. Používaj len videá, ku ktorým máš práva.
