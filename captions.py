"""Build a timed transparent overlay; works with standard Homebrew FFmpeg."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COLORS = {"white": "white", "yellow": "#ffe45e", "lavender": "#debbff"}
SCALES = {"small": 0.040, "medium": 0.054, "large": 0.068}


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
        if begin > cursor:
            timeline.append((blank, begin - cursor))
        name = f'cue-{len(timeline)}.png'
        card(row["text"], size, style).save(directory / name)
        timeline.append((name, finish - begin))
        cursor = finish
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
