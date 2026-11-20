import os, json, uuid, subprocess, shutil, re
from pathlib import Path
from tempfile import TemporaryDirectory
from video_import import download_video, youtube_id
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
UPLOAD = ROOT / 'uploads'; EXPORT = ROOT / 'exports'; DB = ROOT / 'projects.json'
UPLOAD.mkdir(exist_ok=True); EXPORT.mkdir(exist_ok=True)
from credentials import credential, settings
from discovery import discovery
from analysis import analyze, TranscriptionError

app = Flask(__name__)
app.register_blueprint(discovery)
app.register_blueprint(settings)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
ALLOWED = {'.mp4','.mov','.mkv','.webm','.m4v'}

@app.before_request
def restrict_cross_site_api():
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != request.host_url.rstrip('/')):
            return jsonify(error='Otvor CLIPRO v lokálnom okne.'), 403


def load():
    try: return json.loads(DB.read_text())
    except (FileNotFoundError,ValueError): return []
def save(data): DB.write_text(json.dumps(data,indent=2,ensure_ascii=False))
def find(pid): return next((p for p in load() if p['id']==pid),None)
def probe(path):
    if not shutil.which('ffprobe'): return 0
    try:
        out = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,timeout=20,check=True)
        return round(float(out.stdout.strip()),2)
    except (ValueError,subprocess.SubprocessError): return 0

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
    pid=uuid.uuid4().hex[:12]; path=UPLOAD / f'{pid}{ext}'; file.save(path)
    return register_project(pid, path, secure_filename(file.filename))

def register_project(pid, path, name):
    duration=probe(path)
    if not duration:
        path.unlink(missing_ok=True)
        return jsonify(error='Video sa nepodarilo načítať.'),400
    record={'id':pid,'name':name,'source':path.name,'duration':duration,'date':datetime.now().isoformat(timespec='minutes'),'clips':[]}
    data=load(); data.insert(0,record); save(data)
    return jsonify(record),201
@app.post('/api/import')
def import_video():
    data = request.get_json(silent=True)
    video_id = youtube_id(data.get('url') if isinstance(data, dict) else None)
    if not video_id:
        return jsonify(error='Vlož odkaz na konkrétne YouTube video alebo Shorts.'), 400
    pid = uuid.uuid4().hex[:12]
    try:
        with TemporaryDirectory(dir=UPLOAD) as temp:
            source, title = download_video(video_id, Path(temp))
            path = UPLOAD / f'{pid}.mp4'
            source.replace(path)
        return register_project(pid, path, title)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    except OSError:
        return jsonify(error='Video sa nepodarilo uložiť. Skontroluj voľné miesto.'), 500

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
    payload=request.get_json(silent=True) or {}
    try: start=float(payload.get('start',0)); end=float(payload.get('end',30))
    except (ValueError,TypeError):return jsonify(error='Neplatné časové údaje.'),400
    if start < 0 or end<=start or end-start>180 or (p['duration'] and end>p['duration']+.1):return jsonify(error='Rozsah musí mať 1–180 sekúnd a byť v rámci videa.'),400
    layout=payload.get('layout','blur')
    if layout not in ('blur','fill','fit'):return jsonify(error='Neplatný layout.'),400
    hook=str(payload.get('hook','')).strip()[:100]
    cid=uuid.uuid4().hex[:10]; output=EXPORT / f'{cid}.mp4'
    ratio = payload.get('ratio', '9:16')
    sizes = {'9:16': '1080:1920', '1:1': '1080:1080', '16:9': '1920:1080'}
    if ratio not in sizes:
        return jsonify(error='Neplatný pomer strán.'), 400
    size = sizes[ratio]
    fill = f'scale={size}:force_original_aspect_ratio=increase,crop={size}'
    fit = f'scale={size}:force_original_aspect_ratio=decrease'
    if layout == 'fill':
        vf = fill
    elif layout == 'fit':
        vf = f'{fit},pad={size}:(ow-iw)/2:(oh-ih)/2'
    else:
        vf = f'split[bg][fg];[bg]{fill},boxblur=25:5[base];[fg]{fit}[front];[base][front]overlay=(W-w)/2:(H-h)/2'
    vf += ',setsar=1'
    muted = payload.get('muted') is True
    # Hook stored as editable metadata; no font dependencies or unsafe drawtext input.
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(UPLOAD/p['source']),'-t',str(end-start),'-filter_threads','1','-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(output)]
    if muted:
        cmd.insert(-1, '-an')
    try:
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=900)
        if proc.returncode: return jsonify(error='Export zlyhal: '+proc.stderr[-600:]),500
    except subprocess.TimeoutExpired:return jsonify(error='Export prekročil časový limit.'),504
    entry={'id':cid,'name':f'Clip {len(p["clips"])+1}','start':start,'end':end,'layout':layout,'ratio':ratio,'muted':muted,'hook':hook,'file':output.name,'date':datetime.now().isoformat(timespec='minutes')}
    data=load(); next(item for item in data if item['id']==pid)['clips'].insert(0,entry);save(data)
    return jsonify(entry),201
@app.get('/api/export/<cid>')
def export(cid):
    if not re.fullmatch(r'[a-f0-9]{10}',cid):return jsonify(error='Nesprávne ID.'),400
    if not any(c['id']==cid for p in load() for c in p['clips']):return jsonify(error='Klip neexistuje.'),404
    return send_from_directory(EXPORT,cid+'.mp4',as_attachment=True)
@app.delete('/api/projects/<pid>')
def delete(pid):
    data=load(); target=next((p for p in data if p['id']==pid),None)
    if not target:return jsonify(error='Projekt neexistuje.'),404
    (UPLOAD/target['source']).unlink(missing_ok=True)
    for c in target['clips']:(EXPORT/c['file']).unlink(missing_ok=True)
    save([p for p in data if p['id']!=pid]);return jsonify(ok=True)
@app.post('/api/analysis/<pid>')
def project_analysis(pid):
    project = find(pid)
    if not project:
        return jsonify(error='Projekt neexistuje.'), 404
    key = request.headers.get('X-OpenAI-Key', '').strip() or credential('openai')
    if not key or not key.isascii() or not key.isprintable():
        return jsonify(error='Zadaj OpenAI API kľúč v Nastaveniach.'), 400
    try:
        return jsonify(analyze(UPLOAD / project['source'], key))
    except TranscriptionError as exc:
        return jsonify(error=str(exc)), exc.status
    except (OSError, subprocess.SubprocessError):
        return jsonify(error='Skontroluj dostupnosť FFmpeg a zvukovú stopu videa.'), 422
    except (KeyError, TypeError, ValueError):
        return jsonify(error='OpenAI vrátilo neplatný prepis.'), 502

@app.get('/api/health')
def health():return jsonify(ffmpeg=bool(shutil.which('ffmpeg')),projects=len(load()))
if __name__=='__main__':app.run(debug=False,host='127.0.0.1',port=5050)
