import os, json, uuid, subprocess, shutil, re
import math
from threading import RLock
from tempfile import NamedTemporaryFile
from pathlib import Path
from tempfile import TemporaryDirectory
from rendering import edit_options, render, SIZES
from moments import pick_moments
from local_whisper import analyze_local
from video_import import download_video, youtube_id
from datetime import datetime
import io
import wave
from flask import Response, Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv('CLIPRO_DATA_DIR', ROOT)).expanduser().resolve()
DATA.mkdir(exist_ok=True, parents=True)
UPLOAD = DATA / 'uploads'; EXPORT = DATA / 'exports'; DB = DATA / 'projects.json'
library_lock = RLock()
active_analyses = {}
UPLOAD.mkdir(exist_ok=True); EXPORT.mkdir(exist_ok=True)
from credentials import activate, credential, settings
from discovery import discovery, youtube_items, YouTubeError
from analysis import analyze, transcribe, TranscriptionError

app = Flask(__name__)
app.register_blueprint(discovery)
app.register_blueprint(settings)
app.config['TRUSTED_HOSTS'] = ['127.0.0.1', 'localhost', '[::1]']
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
ALLOWED = {'.mp4','.mov','.mkv','.webm','.m4v'}

@app.before_request
def restrict_cross_site_api():
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != request.host_url.rstrip('/')):
            return jsonify(error='Otvor CLIPRO v lokálnom okne.'), 403


class LibraryError(Exception):
    pass


@app.errorhandler(LibraryError)
def library_error(_error):
    return jsonify(error='Knižnica projects.json sa nedá načítať alebo uložiť. Skontroluj súbor a voľné miesto.'), 500


@app.errorhandler(413)
def upload_limit(_error):
    return jsonify(error='Video presahuje limit 2 GB.'), 413


def load() -> list:
    try:
        data = json.loads(DB.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            raise ValueError('Expected project list')
        return data
    except FileNotFoundError:
        return []
    except (ValueError, OSError) as exc:
        raise LibraryError() from exc


def save(data: list) -> None:
    temp = None
    try:
        with NamedTemporaryFile(dir=DB.parent, delete=False, mode='w', encoding='utf-8') as handle:
            temp = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
        temp.replace(DB)
    except OSError as exc:
        raise LibraryError() from exc
    finally:
        if temp:
            temp.unlink(missing_ok=True)


def find(pid):
    return next((p for p in load() if p['id'] == pid), None)


def probe(path: Path) -> float:
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'V:0',
                              '-show_entries', 'stream=codec_type:format=duration',
                              '-of', 'json', str(path)], capture_output=True, text=True,
                             timeout=20, check=True)
        metadata = json.loads(out.stdout)
        duration = float(metadata['format']['duration'])
        if metadata['streams'] and math.isfinite(duration) and duration > 0:
            return round(duration, 3)
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        pass
    return 0


@app.get('/')
def index(): return render_template('index.html')
@app.get('/api/projects')
def projects(): return jsonify(load())
@app.post('/api/upload')
def upload():
    file=request.files.get('file')
    if not file or not file.filename: return jsonify(error='Vyber video.'),400
    ext=Path(secure_filename(file.filename)).suffix.lower()
    if ext not in ALLOWED: return jsonify(error='Nepodporovaný formát videa.'),400
    pid = uuid.uuid4().hex[:12]
    path = UPLOAD / f'{pid}{ext}'
    try:
        file.save(path)
    except OSError:
        path.unlink(missing_ok=True)
        return jsonify(error='Video sa nepodarilo uložiť. Skontroluj voľné miesto.'), 507
    return register_project(pid, path, secure_filename(file.filename))

def register_project(pid, path, name):
    duration=probe(path)
    if not duration:
        path.unlink(missing_ok=True)
        return jsonify(error='Video sa nepodarilo načítať.'),400
    record={'id':pid,'name':name,'source':path.name,'duration':duration,'date':datetime.now().isoformat(timespec='minutes'),'clips':[]}
    try:
        with library_lock:
            data = load()
            data.insert(0, record)
            save(data)
    except LibraryError:
        path.unlink(missing_ok=True)
        raise
    return jsonify(record),201
@app.post('/api/import')
def import_video():
    data = request.get_json(silent=True)
    video_id = youtube_id(data.get('url') if isinstance(data, dict) else None)
    if not video_id:
        return jsonify(error='Vlož odkaz na konkrétne YouTube video alebo Shorts.'), 400
    pid = uuid.uuid4().hex[:12]
    def events():
        yield {'message': 'Pripájam sa k YouTube a načítavam informácie o videu…'}
        try:
            with TemporaryDirectory(dir=UPLOAD) as temp:
                source, title = yield from download_video(video_id, Path(temp))
                yield {'message': 'Pripravujem projekt pre editor…'}
                path = UPLOAD / f'{pid}.mp4'
                source.replace(path)
            response, status = register_project(pid, path, title)
            yield {'status': status, 'result': response.get_json()}
        except ValueError as exc:
            yield {'status': 422, 'result': {'error': str(exc)}}
        except OSError:
            yield {'status': 500, 'result': {'error': 'Video sa nepodarilo uložiť. Skontroluj voľné miesto.'}}

    if request.accept_mimetypes.best == 'application/x-ndjson':
        from flask import stream_with_context
        stream = (json.dumps(event) + '\n' for event in events())
        return Response(stream_with_context(stream), mimetype='application/x-ndjson',
                        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
    for event in events():
        if 'result' in event:
            return jsonify(event['result']), event['status']

@app.get('/api/video/<pid>')
def video(pid):
    p=find(pid)
    if not p:return jsonify(error='Video neexistuje.'),404
    return send_from_directory(UPLOAD,p['source'],conditional=True)
@app.post('/api/clip/<pid>')
def clip(pid):
    p=find(pid)
    if not p:return jsonify(error='Projekt neexistuje.'),404
    if not shutil.which('ffmpeg'):return jsonify(error='FFmpeg nie je nainštalovaný.'),503
    payload = request.get_json(silent=True) if request.data else {}
    if not isinstance(payload, dict):
        return jsonify(error='Neplatné nastavenia klipu.'), 400
    try: start=float(payload.get('start',0)); end=float(payload.get('end',30))
    except (ValueError,TypeError):return jsonify(error='Neplatné časové údaje.'),400
    if not all(map(math.isfinite, (start, end))) or start < 0 or end<=start or end-start>180 or (p['duration'] and end>p['duration']+.1):return jsonify(error='Rozsah musí mať 1–180 sekúnd a byť v rámci videa.'),400
    layout=payload.get('layout','blur')
    if layout not in ('blur','fill','fit'):return jsonify(error='Neplatný layout.'),400
    hook=str(payload.get('hook','')).strip()[:100]
    cid=uuid.uuid4().hex[:10]; output=EXPORT / f'{cid}.mp4'
    ratio = payload.get('ratio', '9:16')
    if not isinstance(ratio, str) or ratio not in SIZES:
        return jsonify(error='Neplatný pomer strán.'), 400
    muted = payload.get('muted') is True
    try:
        edits = edit_options(payload)
        rows = []
        if edits['captions']:
            engine = payload.get('captionEngine', 'local')
            if engine not in ('local', 'openai'):
                raise ValueError('Neplatný zdroj titulkov.')
            language = payload.get('language', 'sk')
            if language not in ('sk', 'auto'):
                raise ValueError('Neplatný jazyk prepisu.')
            cache = transcript_file(pid, engine, language)
            if not cache.is_file():
                raise ValueError('Najprv vytvor prepis v časti Momenty a titulky.')
            rows = json.loads(cache.read_text(encoding='utf-8'))['captions']
        length = render(UPLOAD / p['source'], output, start, end, ratio, layout, muted, edits, rows)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    except (OSError, subprocess.CalledProcessError):
        output.unlink(missing_ok=True)
        app.logger.warning('FFmpeg export failed for project %s', pid)
        return jsonify(error='Export zlyhal. Skontroluj video a voľné miesto na disku.'), 422
    except subprocess.TimeoutExpired:
        output.unlink(missing_ok=True)
        return jsonify(error='Export prekročil časový limit.'), 504
    entry={'id':cid,'name':f'Clip {len(p["clips"])+1}','start':start,'end':end,'layout':layout,'ratio':ratio,'muted':muted,'hook':hook,'file':output.name,'date':datetime.now().isoformat(timespec='minutes')}
    entry.update(duration=length, edits=edits)
    try:
        with library_lock:
            data = load()
            project = next((row for row in data if row['id'] == pid), None)
            if project is None:
                output.unlink(missing_ok=True)
                return jsonify(error='Projekt bol počas exportu odstránený.'), 404
            entry['name'] = f'Klip {len(project["clips"]) + 1}'
            project['clips'].insert(0, entry)
            save(data)
    except LibraryError:
        output.unlink(missing_ok=True)
        raise
    return jsonify(entry),201
@app.get('/api/export/<cid>')
def export(cid):
    if not re.fullmatch(r'[a-f0-9]{10}',cid):return jsonify(error='Nesprávne ID.'),400
    if not any(c['id']==cid for p in load() for c in p['clips']):return jsonify(error='Klip neexistuje.'),404
    return send_from_directory(EXPORT,cid+'.mp4',as_attachment=True)
@app.delete('/api/projects/<pid>')
def delete(pid):
    with library_lock:
        data = load()
        target = next((p for p in data if p['id'] == pid), None)
        if target is None:
            return jsonify(error='Projekt neexistuje.'), 404
        save([p for p in data if p['id'] != pid])
        (UPLOAD / target['source']).unlink(missing_ok=True)
        for engine in ('local', 'openai'):
            (UPLOAD / f'{pid}.{engine}.json').unlink(missing_ok=True)
            for language in ('sk', 'auto'):
                transcript_file(pid, engine, language).unlink(missing_ok=True)
        for clip in target['clips']:
            (EXPORT / clip['file']).unlink(missing_ok=True)
    return jsonify(ok=True)

def transcript_file(pid, engine, language):
    return UPLOAD / f'{pid}.{engine}.{language}.v2.json'


def write_transcript(cache, result):
    with NamedTemporaryFile(dir=UPLOAD, mode='w', encoding='utf-8', delete=False) as tmp:
        temp = Path(tmp.name)
    try:
        temp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        temp.replace(cache)
    finally:
        temp.unlink(missing_ok=True)


@app.patch('/api/analysis/<pid>/caption')
def correct_caption(pid):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not find(pid):
        return jsonify(error='Projekt alebo údaje opravy chýbajú.'), 400
    engine, language = payload.get('engine'), payload.get('language')
    index, text = payload.get('index'), payload.get('text')
    if (engine not in ('local', 'openai') or language not in ('sk', 'auto')
            or type(index) is not int or not isinstance(text, str) or not 0 < len(text.strip()) <= 500):
        return jsonify(error='Zadaj text titulku (1 až 500 znakov).'), 400
    cache = transcript_file(pid, engine, language)
    with library_lock:
        if not cache.is_file():
            return jsonify(error='Prepis sa nenašiel.'), 404
        result = json.loads(cache.read_text(encoding='utf-8'))
        rows = result['captions']
        if not 0 <= index < len(rows) or rows[index]['text'] != payload.get('original'):
            return jsonify(error='Titulok sa zmenil. Načítaj prepis znova.'), 409
        row = rows[index]
        row['text'] = ' '.join(text.split())
        words = row.get('words', [])
        if len(words) == len(row['text'].split()):
            for w, label in zip(words, row['text'].split()):
                w['text'] = label
        else:
            row.pop('words', None)
        result.pop('moments', None)
        write_transcript(cache, result)
    return jsonify(ok=True)


def transcript_response(result, length):
    return jsonify(captions=result['captions'], moments=pick_moments(result['captions'], length))


@app.get('/api/analysis/<pid>/progress')
def analysis_progress(pid):
    language = request.args.get('language', 'sk')
    if language not in ('sk', 'auto') or not re.fullmatch(r'[a-f0-9]{12}', pid):
        return jsonify(error='Neplatná požiadavka.'), 400
    cache = transcript_file(pid, 'local', language)
    with library_lock:
        progress = active_analyses.get(cache)
    return jsonify(progress=progress), 200, {'Cache-Control': 'no-store'}


@app.post('/api/analysis/<pid>')
def project_analysis(pid):
    project = find(pid)
    if not project:
        return jsonify(error='Projekt neexistuje.'), 404
    payload = request.get_json(silent=True)
    engine = payload.get('engine') if isinstance(payload, dict) else 'openai'
    if engine not in ('local', 'openai'):
        return jsonify(error='Vyber spôsob prepisu.'), 400
    options = payload if isinstance(payload, dict) else {}
    language = options.get('language', 'sk')
    length = options.get('momentLength', 30)
    if language not in ('sk', 'auto') or length not in (15, 30, 60):
        return jsonify(error='Vyber podporovaný jazyk a dĺžku momentu.'), 400
    cache = transcript_file(pid, engine, language)
    with library_lock:
        if cache.is_file():
            try:
                return transcript_response(json.loads(cache.read_text(encoding='utf-8')), length)
            except (ValueError, OSError):
                return jsonify(error='Uložený prepis sa nedá načítať. Skontroluj súbor prepisu v uploads.'), 500
        if cache in active_analyses:
            return jsonify(error='Prepis tohto projektu už prebieha.'), 409
        active_analyses[cache] = None
    try:
        if engine == 'local':
            def progress(part, total):
                with library_lock:
                    active_analyses[cache] = dict(part=part, total=total)
            result = analyze_local(UPLOAD / project['source'], project['duration'], language, progress)
        else:
            key = request.headers.get('X-OpenAI-Key', '').strip() or credential('openai')
            if not key or not key.isascii() or not key.isprintable():
                return jsonify(error='Zvoľ lokálny prepis alebo zadaj OpenAI API kľúč.'), 400
            result = analyze(UPLOAD / project['source'], key, language)
        with library_lock:
            if find(pid) is None:
                return jsonify(error='Projekt bol odstránený.'), 404
            write_transcript(cache, result)
        return transcript_response(result, length)
    except TranscriptionError as exc:
        return jsonify(error=str(exc)), exc.status
    except (OSError, subprocess.SubprocessError):
        return jsonify(error='Skontroluj dostupnosť FFmpeg a zvukovú stopu videa.'), 422
    except (KeyError, TypeError, ValueError):
        return jsonify(error='Prepis sa nepodarilo spracovať.'), 502
    finally:
        with library_lock:
            active_analyses.pop(cache, None)

@app.post('/api/settings/<provider>/test')
def test_service(provider):
    if provider not in ('openai', 'youtube'):
        return jsonify(error='Neznáma služba.'), 404
    payload = request.get_json()
    candidate = payload.get('key', '') if isinstance(payload, dict) else ''
    if not isinstance(candidate, str):
        return jsonify(error='Skontroluj formát kľúča.'), 400
    key = candidate.strip() or credential(provider)
    if not key or not key.isascii() or not key.isprintable() or any(c.isspace() for c in key):
        return jsonify(error='Vlož platný API kľúč.'), 400
    try:
        if provider == 'youtube':
            youtube_items(key, limit=1)
            if candidate.strip():
                activate(provider, key)
            return jsonify(message='YouTube Data API odpovedalo. Kľúč funguje pre Trend Radar.')
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as sample:
            sample.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            sample.writeframes(bytes(2 * 16000 * 2))
        audio.seek(0)
        transcribe(audio, 'test.wav', key, read_timeout=30)
        if candidate.strip():
            activate(provider, key)
        return jsonify(message='Whisper úspešne spracoval testovací zvuk.')
    except (TranscriptionError, YouTubeError) as exc:
        return jsonify(error=str(exc)), exc.status
    except (ValueError, KeyError, TypeError):
        return jsonify(error='Služba vrátila neplatnú odpoveď.'), 502


@app.get('/api/health')
def health():return jsonify(ffmpeg=bool(shutil.which('ffmpeg')),projects=len(load()))
if __name__=='__main__':app.run(debug=False,host='127.0.0.1',port=5050)
