from functools import lru_cache

@lru_cache(maxsize=1)
def speech_model():
    from faster_whisper import WhisperModel
    return WhisperModel("tiny", device="cpu", compute_type="int8")

def analyze(path):
    segments, _ = speech_model().transcribe(str(path), beam_size=1)
    rows = [dict(start=round(s.start, 3), end=round(s.end, 3), text=s.text.strip()) for s in segments if s.text.strip()]
    # Prefer dense speech and questions. Keep suggestions distinct in time.
    ranked = sorted(rows, key=lambda r: (int("?" in r["text"]), len(r["text"].split()) / max(1, r["end"]-r["start"])), reverse=True)
    moments = []
    for row in ranked:
        if all(abs(row["start"] - other["start"]) >= 25 for other in moments):
            moments.append(row)
        if len(moments) == 5:
            break
    return dict(captions=rows, moments=moments)
