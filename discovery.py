import re

import requests
from flask import Blueprint, jsonify, request

from credentials import credential

discovery = Blueprint("discovery", __name__)


class YouTubeError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def youtube_items(key, channel="", limit=10):
    params = {"part": "snippet", "maxResults": limit}
    if channel:
        endpoint = "search"
        params.update(channelId=channel, eventType="live", type="video")
    else:
        endpoint = "videos"
        params.update(chart="mostPopular", regionCode="SK")
    try:
        response = requests.get("https://www.googleapis.com/youtube/v3/" + endpoint,
                                params=params, headers={"X-Goog-Api-Key": key},
                                timeout=(5, 15), allow_redirects=False)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise YouTubeError("Nepodarilo sa spojiť s YouTube Data API. Skontroluj internetové pripojenie.", 502) from None
    if response.status_code == 200 and isinstance(payload.get("items"), list):
        return payload["items"]
    error = payload.get("error", {})
    reasons = {entry.get("reason") for field in ("details", "errors") for entry in error.get(field, [])}
    if reasons & {"accessNotConfigured", "SERVICE_DISABLED"}:
        message = "V Google Cloud zapni YouTube Data API v3 pre projekt tohto kľúča."
    elif reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}:
        message = "YouTube hlási vyčerpanú kvótu. Skontroluj kvóty projektu v Google Cloud."
    elif reasons & {"API_KEY_INVALID", "keyInvalid"}:
        message = "Google odmietol kľúč. Skopíruj API kľúč z projektu v Google Cloud."
    elif response.status_code == 403:
        message = "Google zamietol prístup. Skontroluj povolenie pre YouTube Data API v3 a obmedzenia kľúča pre lokálnu serverovú aplikáciu."
    else:
        message = f"YouTube Data API vrátilo chybu HTTP {response.status_code}."
    raise YouTubeError(message, response.status_code if response.status_code in (400, 401, 403, 429) else 502)


@discovery.get("/api/discovery")
def discover():
    key = credential("youtube")
    if not key:
        return jsonify(error="Zadaj YouTube API kľúč v Nastaveniach."), 400
    channel = request.args.get("channel", "").strip()
    if channel and not re.fullmatch(r"UC[\w-]{22}", channel):
        return jsonify(error="Zadaj ID kanála YouTube začínajúce UC."), 400
    try:
        items = youtube_items(key, channel)
        return jsonify([dict(title=i["snippet"]["title"], video=i["id"]["videoId"] if channel else i["id"]) for i in items])
    except YouTubeError as exc:
        return jsonify(error=str(exc)), exc.status
