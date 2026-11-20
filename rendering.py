"""Render only the selected source interval. All effects use the same input clock."""
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from captions import COLORS, SCALES, overlay_manifest

SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}


def choice(payload: dict, name: str, default: str, options) -> str:
    value = payload.get(name, default)
    if not isinstance(value, str) or value not in options:
        raise ValueError("Neplatná voľba v nastavení klipu.")
    return value


def edit_options(payload: dict) -> dict:
    return dict(zoom=choice(payload, "zoom", "none", ("none", "close", "punch")),
                silence=choice(payload, "silence", "off", ("off", "0.8", "1.5")),
                captions=payload.get("captions") is True,
                color=choice(payload, "color", "white", COLORS),
                size=choice(payload, "size", "medium", SCALES),
                position=choice(payload, "position", "bottom", ("top", "center", "bottom")))


def silent_ranges(input_args: list, duration: float, minimum: str) -> list:
    proc = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *input_args,
                           "-map", "0:a:0", "-af", f"silencedetect=n=-38dB:d={minimum}",
                           "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    if proc.returncode:
        raise ValueError("Na strih ticha je potrebná čitateľná zvuková stopa.")
    intervals = []
    start = None
    for kind, time in re.findall(r"silence_(start|end): ([-.\deE+]+)", proc.stderr):
        mark = max(0.0, min(duration, float(time)))
        if kind == "start":
            start = mark
        elif start is not None:
            intervals.append((start, mark))
            start = None
    if start is not None:
        intervals.append((start, duration))
    if duration - sum(b-a for a,b in intervals) < .08:
        raise ValueError("Celý výber je tichý. Vypni strih ticha alebo vyber iný úsek.")
    # Keep short natural transitions at speech boundaries.
    return [(a + .10 if a > .02 else a, b - .10 if b < duration - .02 else b)
            for a, b in intervals if b-a > .20]


def time_filter(cuts: list, audio: bool) -> str:
    if not cuts:
        return "anull" if audio else "null"
    skip = "+".join(f"gte(t,{a:.6f})*lt(t,{b:.6f})" for a, b in cuts)
    removed = "+".join(f"gte(T,{b:.6f})*{b-a:.6f}" for a, b in cuts)
    prefix = "a" if audio else ""
    return f"{prefix}select='not({skip})',{prefix}setpts='PTS-({removed})/TB'"


def render(source: Path, output: Path, start: float, end: float, ratio: str,
           layout: str, muted: bool, edits: dict, rows: list) -> float:
    width, height = SIZES[ratio]
    size = f"{width}:{height}"
    duration = end - start
    inputs = ["-ss", str(start), "-t", str(duration), "-i", str(source)]
    cuts = silent_ranges(inputs, duration, edits["silence"]) if edits["silence"] != "off" else []
    fill = f"scale={size}:force_original_aspect_ratio=increase,crop={size}"
    fit = f"scale={size}:force_original_aspect_ratio=decrease"
    if layout == "fill":
        graph = f"[0:v:0]{fill}"
    elif layout == "fit":
        graph = f"[0:v:0]{fit},pad={size}:(ow-iw)/2:(oh-ih)/2"
    else:
        graph = f"[0:v:0]split[bg][fg];[bg]{fill},boxblur=25:5[base];[fg]{fit}[front];[base][front]overlay=(W-w)/2:(H-h)/2"
    graph += ",setsar=1"
    close = f"crop=trunc(iw/1.25/2)*2:trunc(ih/1.25/2)*2,scale={size}"
    if edits["zoom"] == "close":
        graph += "," + close
    elif edits["zoom"] == "punch":
        graph += f"[laid];[laid]split[wide][in];[in]{close}[near];[wide][near]overlay=enable='between(mod(t,6),2,3.5)'"
    with TemporaryDirectory(dir=output.parent) as tmp:
        if edits["captions"]:
            manifest = overlay_manifest(Path(tmp), rows, start, end, (width, height), edits)
            inputs += ["-f", "concat", "-safe", "1", "-i", str(manifest)]
            graph += "[frame];[frame][1:v]overlay=eof_action=pass"
        graph += "," + time_filter(cuts, False) + "[video]"
        maps = ["-map", "[video]"]
        if not muted and cuts:
            graph += ";[0:a:0]" + time_filter(cuts, True) + "[audio]"
            maps += ["-map", "[audio]"]
        elif not muted:
            maps += ["-map", "0:a:0?"]
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex_threads", "1",
                        "-filter_complex", graph, *maps, "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", str(output)], capture_output=True, check=True, timeout=900)
    return round(duration - sum(b-a for a,b in cuts), 3)
