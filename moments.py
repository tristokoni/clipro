"""Find bounded, non-overlapping excerpts across the complete transcript."""
import re

QUESTION = re.compile(r"\b(prečo|ako|vieš|vedeli ste|čo ak|how|why)\b", re.I)


def cue_groups(words: list) -> list:
    rows, group = [], []
    for word in words:
        if group and (word["start"] - group[-1]["end"] > .65 or
                      word["end"] - group[0]["start"] > 5 or len(group) >= 12):
            rows.append(make_cue(group))
            group = []
        group.append(word)
        if word["text"].rstrip().endswith((".", "!", "?")):
            rows.append(make_cue(group))
            group = []
    if group:
        rows.append(make_cue(group))
    return rows


def make_cue(words):
    return dict(start=words[0]["start"], end=words[-1]["end"],
                text=" ".join(w["text"] for w in words), words=words)


def pick_moments(rows: list, target: int = 30) -> list:
    candidates = []
    for i, first in enumerate(rows):
        start, previous, speech, count = first["start"], first["start"], 0., 0
        best = None
        question = bool(QUESTION.search(first["text"]) or "?" in first["text"])
        boundary = i == 0 or start - rows[i-1]["end"] > .5 or rows[i-1]["text"].endswith((".", "!", "?"))
        for j in range(i, len(rows)):
            row = rows[j]
            length = row["end"] - start
            if j > i and (row["start"] - previous > 2.5 or length > target * 1.45):
                break
            previous = row["end"]
            speech += max(0, row["end"] - row["start"])
            count += len(row["text"].split())
            if length <= 0 or length > 180:
                continue
            complete = row["text"].rstrip().endswith((".", "!", "?"))
            score = (2.7 * (1 - abs(length-target)/target) + .7*question +
                     .45*complete + .4*boundary + .55*min(1, speech/length) +
                     .4*min(1, count / max(1, length * 2)))
            if best is None or score > best[0]:
                best = score, j, complete
        if best:
            score, j, complete = best
            text = " ".join(r["text"] for r in rows[i:j+1])
            reason = "Otázka na úvod" if question else "Ukončená veta" if complete else "Súvislá reč"
            candidates.append((score, dict(start=start, end=rows[j]["end"], text=text, reason=reason)))

    selected = []
    span = rows[-1]["end"] - rows[0]["start"] if rows else 0
    while candidates and len(selected) < 5:
        def priority(candidate):
            score, item = candidate
            distance = min((abs(other["start"] - item["start"]) for other in selected), default=span)
            return score + .8 * min(1, distance / max(target, span / 5))
        _, pick = max(candidates, key=priority)
        selected.append(pick)
        candidates = [(s,m) for s,m in candidates if m["end"] <= pick["start"] or m["start"] >= pick["end"]]
    return selected
