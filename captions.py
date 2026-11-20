"""Build a timed transparent overlay; works with standard Homebrew FFmpeg."""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COLORS = {"white": "white", "yellow": "#ffe45e", "lavender": "#debbff"}
SCALES = {"small": 0.040, "medium": 0.054, "large": 0.068}


@lru_cache(maxsize=96)
def caption_font(size: int):
    for name in ("Arial Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def card(text: str, size: tuple, style: dict) -> Image.Image:
    width, height = size
    px = round(min(size) * SCALES[style["size"]])
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    # Reduce font size for an unusually long cue so all lines stay on screen.
    while True:
        font = caption_font(px)
        lines = [""]
        for word in text.split():
            candidate = (lines[-1] + " " + word).strip()
            if lines[-1] and draw.textlength(candidate, font) > width * .88:
                lines.append(word)
            else:
                lines[-1] = candidate
        content = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), content, font=font, align="center")
        if (bounds[2] - bounds[0] < width * .94 and bounds[3] - bounds[1] < height * .75) or px <= 12:
            break
        px = max(12, int(px * .85))
    h = bounds[3] - bounds[1]
    y = {"bottom": height * .90 - h, "center": (height - h) / 2, "top": height * .10}[style["position"]]
    x = (width - bounds[2] - bounds[0]) / 2
    draw.multiline_text((x, y - bounds[1]), content, font=font, align="center",
                        fill=COLORS[style["color"]], stroke_width=max(2, px // 15), stroke_fill="black")
    return image


def word_timeline(row):
    if row.get("words"):
        return row["words"]
    words = row["text"].split()
    total = sum(map(len, words))
    cursor = row["start"]
    result = []
    for word in words:
        end = cursor + (row["end"] - row["start"]) * len(word) / total
        result.append(dict(text=word, start=cursor, end=end))
        cursor = end
    return result


def motion_states(row, motion):
    words = word_timeline(row)
    for i in range(0, len(words), 3):
        group = words[i:i+3]
        labels = [w["text"] for w in group]
        start = group[0]["start"]
        end = words[i+3]["start"] if i+3 < len(words) else row["end"]
        if motion == "karaoke":
            for k, word in enumerate(group):
                until = group[k+1]["start"] if k+1 < len(group) else end
                yield word["start"], until, labels, k, 1.
        else:
            attack = min(.20, (end-start)*.6)
            keys = [(0., .82), (.27, .98), (.50, 1.10), (.76, 1.04), (1., 1.)]
            for k, (part, scale) in enumerate(keys):
                until = start + attack*keys[k+1][0] if k+1 < len(keys) else end
                yield start + attack*part, until, labels, None, scale


def kinetic_card(words, active, scale, size, style):
    width, height = size
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    labels = [word.upper() for word in words] if active is None else words
    base = round(min(size) * SCALES[style["size"]] * 1.15)
    font = caption_font(base)
    max_width = draw.textlength("  ".join(labels), font=font)
    px = max(8, round(base * min(1., width*.78/max(1., max_width)) * scale))
    font = caption_font(px)
    gap = draw.textlength("  ", font=font)
    lengths = [draw.textlength(word, font=font) for word in labels]
    x = (width - sum(lengths) - gap*(len(labels)-1))/2
    y = round(height * {"top": .15, "center": .50, "bottom": .85}[style["position"]])
    accent = COLORS[style["color"]]
    for i, (word, length) in enumerate(zip(labels, lengths)):
        if i == active:
            draw.rounded_rectangle((x-px*.13, y-px*.66, x+length+px*.13, y+px*.68),
                                   radius=px*.24, fill=accent)
        fill = "#201629" if i == active else accent if active is None else "white"
        stroke = 0 if i == active else max(2, px//15)
        draw.text((x, y), word, font=font, anchor="lm", fill=fill,
                  stroke_width=stroke, stroke_fill="#201629")
        x += length + gap
    return image


def overlay_manifest(directory: Path, rows: list, start: float, end: float,
                     size: tuple, style: dict) -> Path:
    blank = "blank.png"
    Image.new("RGBA", size).save(directory / blank)
    timeline = []
    cursor = start
    for row in rows:
        begin = max(cursor, start, row["start"])
        finish = min(end, row["end"])
        if finish <= begin:
            continue
        motion = style.get("motion", "classic")
        states = ([(begin, finish, None, None, 1.)] if motion == "classic"
                  else motion_states(row, motion))
        for a, b, words, active, scale in states:
            a, b = max(cursor, begin, a), min(finish, b)
            if b <= a:
                continue
            if a > cursor:
                timeline.append((blank, a - cursor))
            name = f'cue-{len(timeline)}.png'
            frame = (card(row["text"], size, style) if words is None
                     else kinetic_card(words, active, scale, size, style))
            frame.save(directory / name, compress_level=1)
            timeline.append((name, b - a))
            cursor = b
    if not any(name != blank for name, _ in timeline):
        raise ValueError("Vo vybranom úseku nie sú titulky. Zmeň rozsah alebo vypni titulky.")
    if end > cursor:
        timeline.append((blank, end - cursor))
    lines = ["ffconcat version 1.0"]
    for name, duration in timeline:
        lines.extend([f"file {name}", f"duration {duration:.6f}"])
    lines.append(f"file {blank}")
    manifest = directory / "captions.ffconcat"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest
