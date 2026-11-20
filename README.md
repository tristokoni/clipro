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

## Architektúra

Flask obsluhuje dashboard a projektové API. FFmpeg číta lokálne médiá a renderuje spoločný výstup 9:16 pre TikTok, Reels a Shorts. Súbory ostávajú v uploads a exports, metadáta v projects.json. Táto verzia je určená pre jedného používateľa.

Modul analysis.py používa faster-whisper na prepis reči. V aktívnom virtuálnom prostredí spusti pip install -r requirements-ai.txt. Prvé použitie vyžaduje stiahnutie modelu tiny z Hugging Face. Obrazovka momentov ponúkne SRT pre celé zdrojové video a úseky vybrané podľa hustoty reči a otázok.

Modul discovery.py používa YouTube Data API v3. Nastav na serveri premennú YOUTUBE_API_KEY. Radar zobrazuje slovenský rebríček mostPopular. Po zadaní ID kanála kontroluje otvorená stránka živé vysielanie každých päť minút.
