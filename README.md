# CLIPRO

Lokálne slovenské videoštúdio pre tvorcov krátkych klipov. Otvor video, označ úsek, nastav obraz, ticho a titulky a exportuj MP4. Bezplatný režim používa whisper.cpp na tvojom počítači. Na lokálny prepis ani export nepotrebuješ účet či API kľúč.

## Spustenie na Macu

Stiahni [CLIPRO-Mac.zip](https://github.com/tristokoni/clipro/raw/refs/heads/main/CLIPRO-Mac.zip), rozbaľ ho a otvor **Spustit CLIPRO.command**. Spúšťač používa Python 3.10+, nainštaluje závislosti do projektového prostredia a otvorí lokálnu adresu v prehliadači. Okno Terminálu nechaj otvorené. Na inštaláciu chýbajúcich systémových nástrojov používa [Homebrew](https://brew.sh/).

Pri spustení z GitHubu potrebuješ Git a Homebrew.

```bash
git clone https://github.com/tristokoni/clipro.git
cd clipro
bash "Spustit CLIPRO.command"
```

Pri aktualizácii existujúceho klonu ukonči bežiace štúdio cez Ctrl+C, spusti `git pull --ff-only` a znova otvor spúšťač. Pri inštalácii z nového ZIPu zachovaj starý priečinok. Ak chceš pracovať s rovnakou knižnicou, nastav `CLIPRO_DATA_DIR` na absolútnu cestu k starému priečinku obsahujúcemu projects.json, uploads a exports. Jednu knižnicu používaj naraz v jednej bežiacej inštancii.

## Prvý klip a titulky

1. V **Prehľade** nahraj video do 2 GB alebo vlož odkaz na ukončené verejné YouTube video. Import z YouTube používa yt-dlp. Dostupnosť videa závisí od YouTube.
2. V **Editore klipov** označ začiatok a koniec (najviac 180 sekúnd). Vyber pomer strán, spôsob orezania a zvuk. Detail zväčší obraz okolo stredu o 25 %. Striedavý detail sa zapne od druhej do 3,5. sekundy každého šesťsekundového cyklu zdrojového výberu.
3. **Vystrihnúť ticho** vyhľadá úseky pod −38 dB dlhšie než zvolených 0,8 alebo 1,5 sekundy. Skráti obraz aj zvuk a pri reči ponechá približne 0,1 sekundy na prechod. Funguje aj pri stlmenom exporte, pokiaľ zdroj obsahuje zvuk.
4. Zapni **Vložiť titulky do MP4**. Vyber farbu, veľkosť a polohu. Pri prvom použití CLIPRO stiahne viacjazyčný model small-q5_1 (190 MB) a overí jeho kontrolný súčet. Následný prepis a export fungujú aj bez internetu. Celý zdroj prepíše raz a ďalšie klipy použijú uložené časové značky. Vizuálny štýl sa zapisuje do obrazu MP4.
5. Vygeneruj klip a stiahni ho cez **MP4**. **Momenty a titulky** ponúkajú aj prepis pôvodného videa vo formáte SRT a návrhy úsekov. SRT používa čas pôvodného videa. Po vystrihnutí páuz sú titulky priamo v exportovanom obraze zosúladené so strihom.

## Manuálne spustenie

Nainštaluj Python 3.10+, FFmpeg s ffprobe a whisper.cpp s príkazom `whisper-cli`. Na Macu:

```bash
brew install python ffmpeg whisper.cpp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Otvor http://127.0.0.1:5050. Voliteľný import z YouTube potrebuje yt-dlp s jeho YouTube komponentmi a podporovaný JavaScript runtime (napríklad Deno). Dvojklikový spúšťač tieto nástroje pripraví. Automatický prepis, SRT a MP4 z vlastného súboru fungujú samostatne.

## Uloženie a nastavenia

| Premenná | Použitie |
| --- | --- |
| CLIPRO_DATA_DIR | Priečinok knižnice. Predvolene je to priečinok aplikácie. Obsahuje projects.json, zdrojové médiá a exporty. |
| CLIPRO_WHISPER_MODEL | Voliteľná cesta k existujúcemu viacjazyčnému modelu GGML pre whisper.cpp. Väčší model môže zlepšiť slovenčinu za cenu vyššej náročnosti. Zmena modelu platí pre nové prepisy. |
| XDG_CACHE_HOME | Priečinok cache. Predvolený model je v ~/.cache/clipro/ggml-small-q5_1.bin. |
| OPENAI_API_KEY | Len pre výslovne zvolený platený cloudový prepis. |
| YOUTUBE_API_KEY | Len pre Trend Radar cez YouTube Data API v3. |

Premenné nastav v Termináli pred spustením. Súbor .env.example uvádza príklady. Aplikácia súbory .env automaticky nenačítava. Kľúče môžeš zadať aj v Nastaveniach do pamäte relácie alebo macOS Kľúčenky. Prepisy sú v uploads vedľa zdroja a pri odstránení projektu sa zmažú spolu s ním.

## Riešenie problémov

- **OpenAI hlási nulový kredit.** V časti Momenty a titulky vyber **Lokálne · zadarmo**. Titulky v editore túto možnosť používajú automaticky.
- **Prvé použitie potrebuje internet.** Po prerušení sťahovania skús prepis znova alebo zadaj cestu k už stiahnutému modelu cez CLIPRO_WHISPER_MODEL.
- **Chýba whisper-cli.** Spusti `brew install whisper.cpp` a otvor spúšťač znova. Stav overíš cez `whisper-cli --help`.
- **Video nemá zvuk alebo celý výber tvorí ticho.** Vypni strih ticha aj automatické titulky alebo vyber časť s rečou.
- **Video z YouTube sa nedá stiahnuť.** Pri súkromnom videu, živom prenose alebo obmedzení prístupu použi vlastný zdrojový súbor. API kľúč pre Radar sťahovanie neodomkne.
- **Model vynechal alebo skomolil slová.** V časti Momenty a titulky otvor Opraviť text titulkov, vyber čas a ulož opravu. Presnosť závisí od reči, šumu a jazyka. Pre nové prepisy môžeš použiť väčší model.

## Kontroly

```bash
python -m unittest discover -s tests -v
```

Testy pracujú v dočasných priečinkoch. Kontrola exportu používa systémové FFmpeg a ffprobe. Platené služby ani kľúče nepotrebuješ.


## Slovenské titulky, pohyb a výber momentov

Jazyk reči je predvolene **Slovenčina** (kód sk). Pre iný hovorený jazyk vyber **Automaticky podľa reči**. Nastavenie jazyka určuje prepis hovorenej reči. Staršie automatické prepisy zostávajú na disku a pre túto verziu sa vytvorí nový prepis. Ak máš vlastný model cez CLIPRO_WHISPER_MODEL, potrebuješ viacjazyčnú verziu.

V editore vyber **Karaoke** na zvýrazňovanie slov farebnou bublinou, **Pop** na krátke pulzujúce frázy alebo **Klasické** pre statický text. Lokálny prepis poskytuje odhad časov jednotlivých slov. Pri cloudových titulkoch a opravách so zmeneným počtom slov sa čas rozdelí v rámci titulku. Nastavenia farby, veľkosti a polohy platia pre všetky tri štýly.

V **AI momenty** vyber cieľ 15, 30 alebo 60 sekúnd. CLIPRO hľadá v celom prepise súvislé úseky blízke zvolenej dĺžke, uprednostní prirodzené hranice viet, otázky a súvislú reč a ponúkne najviac päť neprekrývajúcich sa výberov. Karta ukazuje rozsah aj text. **Otvoriť úsek v editore** prenesie oba časy a umožní strih doladiť. Zmena cieľovej dĺžky využije už vytvorený prepis.

V rovnakej obrazovke môžeš opraviť text konkrétneho titulku. Oprava platí pre vybraný jazyk a zdroj prepisu, pre nové SRT aj nové exporty. Vytvorené MP4 zostávajú samostatné súbory.
