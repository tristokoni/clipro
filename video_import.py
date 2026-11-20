import re
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit


def youtube_id(url):
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
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
        '--match-filter', '!is_live & !is_upcoming', '--max-filesize', '2G',
        '--socket-timeout', '20', '--retries', '2', '--no-progress',
        '-f', 'bv[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/bv+ba/b',
        '--merge-output-format', 'mp4', '--remux-video', 'mp4',
        '-o', str(directory / 'source.%(ext)s'), '--print', 'after_move:title',
        'https://www.youtube.com/watch?v=' + video_id,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise ValueError('Sťahovanie prekročilo časový limit 30 minút.') from None
    if result.returncode:
        raise ValueError('YouTube video nesprístupnil. Skontroluj odkaz, pripojenie a aktualizáciu yt-dlp.')
    path = directory / 'source.mp4'
    if not path.is_file() or path.stat().st_size > 2 * 1024**3:
        raise ValueError('Vyber ukončené video s veľkosťou do 2 GB.')
    return path, result.stdout.strip()[:200] or video_id
