import json
import os
import re
import selectors
import signal
import time
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit


def youtube_id(url):
    if not isinstance(url, str):
        return None
    try:
        value = url.strip()
        parts = urlsplit(value if '://' in value else 'https://' + value)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https'):
        return None
    if host == 'youtu.be':
        candidate = parts.path.lstrip('/')
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        if parts.path == '/watch':
            candidate = parse_qs(parts.query).get('v', [''])[0]
        else:
            match = re.fullmatch(r'/(?:shorts|live|embed)/([^/]+)/?', parts.path)
            candidate = match[1] if match else ''
    else:
        return None
    return candidate if re.fullmatch(r'[A-Za-z0-9_-]{11}', candidate) else None


def download_video(video_id, directory):
    executable = shutil.which('yt-dlp')
    if not executable:
        raise ValueError('Chýba yt-dlp. Na Macu znova otvor Spustit CLIPRO.command.')
    cmd = [
        executable, '--ignore-config', '--no-playlist', '--no-simulate',
        '--match-filter', "!is_live & live_status!=?is_upcoming", '--max-filesize', '2G',
        '--socket-timeout', '15', '--retries', '2', '--newline', '--progress',
        '--progress-delta', '1', '--color', 'never',
        '--progress-template', 'download:PROGRESS %(progress.downloaded_bytes)s %(progress._percent_str)s',
        '--progress-template', 'postprocess:PROCESSING',
        '-f', 'bv[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/bv+ba/b',
        '--merge-output-format', 'mp4', '--remux-video', 'mp4',
        '-o', str(directory / 'source.%(ext)s'), '--print', 'after_move:TITLE %(title)j',
        'https://www.youtube.com/watch?v=' + video_id,
    ]
    title = video_id
    last_error = ''
    started = last_activity = time.monotonic()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=True) as proc, selectors.DefaultSelector() as poll:
        try:
            poll.register(proc.stdout, selectors.EVENT_READ)
            pending = b''
            while True:
                now = time.monotonic()
                if now - last_activity > 120 or now - started > 1800:
                    raise ValueError('Sťahovanie prekročilo časový limit. Skontroluj pripojenie a skús to znova.')
                if not poll.select(2):
                    yield {'type': 'heartbeat'}
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                last_activity = now
                pending += chunk
                lines = pending.split(b'\n')
                pending = lines.pop()
                for raw in lines:
                    line = raw.decode('utf-8', 'replace').strip()
                    if line.startswith('PROGRESS '):
                        fields = line.split()
                        if len(fields) >= 3:
                            size = int(fields[1]) if fields[1].isdigit() else 0
                            yield {'message': f'Sťahujem stopu · {size / 1048576:.1f} MB · {fields[2]}'}
                    elif line.startswith('PROCESSING'):
                        yield {'message': 'Spracúvam stiahnuté video…'}
                    elif line.startswith('TITLE '):
                        title = json.loads(line[6:])
                    elif line.startswith('ERROR:'):
                        last_error = re.sub(r'https?://\S+', '[odkaz]', line[6:]).strip()[:360]
            if proc.wait():
                detail = last_error.lower()
                if 'private video' in detail or 'unavailable' in detail or 'members-only' in detail:
                    raise ValueError('Video nie je verejne dostupné. Ak máš zdrojový súbor, otvor ho cez Vybrať súbor.')
                if 'sign in' in detail:
                    raise ValueError('YouTube vyžaduje prihlásenie pre toto video alebo pripojenie. V editore môžeš otvoriť vlastný súbor.')
                raise ValueError('Sťahovanie zlyhalo. ' + (last_error or 'Skontroluj pripojenie a dostupnosť videa.'))
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    path = directory / 'source.mp4'
    if not path.is_file() or path.stat().st_size > 2 * 1024**3:
        raise ValueError('Vyber ukončené video s veľkosťou do 2 GB.')
    return path, title[:200]
