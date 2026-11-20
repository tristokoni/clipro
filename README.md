# CLIPRO — video clipping dashboard

Lokálna webová aplikácia na upload videí, výber momentov a export klipov (9:16, 1:1 a 16:9). Skutočný export zabezpečuje FFmpeg, nie demo dáta.

Na Macu rozbaľ CLIPRO-Mac.zip a otvor **Spustit CLIPRO.command**. V Nastaveniach môžeš uložiť alebo odstrániť API kľúče pre OpenAI a YouTube. Na macOS sa ukladajú do Kľúčenky. Na ostatných systémoch zostanú v pamäti do vypnutia aplikácie.

## Manuálne spustenie

1. Nainštaluj Python 3.10+ a FFmpeg (`brew install ffmpeg` na macOS, `winget install Gyan.FFmpeg` na Windows).
2. V priečinku projektu spusti:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

3. Otvor http://127.0.0.1:5050

## Import z YouTube

V Prehľade vlož odkaz na konkrétne video alebo Shorts a klikni na **Stiahnuť do editora**. Rovnaké tlačidlo nájdeš pri videách v Trend Radare. Na Macu spúšťač doinštaluje yt-dlp cez Homebrew. Pri manuálnom spustení musí byť yt-dlp dostupný v PATH. Import podporuje ukončené verejne dostupné videá do 2 GB.

## Čo funguje
- Upload vlastných MP4/MOV/MKV/WEBM/M4V súborov (max 2 GB)
- Video prehrávač, označenie začiatku/konca, výber 15/30/60 sekúnd, tri pomery strán a tri režimy obrazu
- Export MP4 so zvukom alebo bez zvuku (H.264) a stiahnutie
- Lokálna knižnica projektov a klipov, vymazanie
- Dashboard so skutočnými počtami

## Architektúra

Flask obsluhuje dashboard a projektové API. FFmpeg číta lokálne médiá a renderuje výstup vo zvolenom pomere strán pre TikTok, Reels a Shorts. Súbory ostávajú v uploads a exports, metadáta v projects.json. Táto verzia je určená pre jedného používateľa.

V časti Momenty a titulky vyber projekt a spusti analýzu. FFmpeg pripraví zvuk a aplikácia ho odošle na prepis modelu whisper-1. Obrazovka momentov ponúkne SRT pre celé zdrojové video a úseky vybrané podľa hustoty reči a otázok.

Modul discovery.py používa YouTube Data API v3. Kľúč zadaj v Nastaveniach. Radar zobrazuje slovenský rebríček mostPopular. Po zadaní ID kanála kontroluje otvorená stránka živé vysielanie každých päť minút.
