import json
from credentials import credential
import re
from urllib.parse import urlencode
from urllib.request import urlopen
from flask import Blueprint, jsonify, request

discovery = Blueprint("discovery", __name__)

@discovery.get("/api/discovery")
def discover():
    key = credential("youtube")
    if not key:
        return jsonify(error="Zadaj YouTube API kľúč v Nastaveniach."), 503
    channel = request.args.get("channel", "").strip()
    params = dict(key=key, part="snippet", maxResults=10)
    if channel:
        if not re.fullmatch(r"UC[\w-]{22}", channel):
            return jsonify(error="Zadaj ID kanála YouTube začínajúce UC."), 400
        endpoint = "search"
        params.update(channelId=channel, eventType="live", type="video")
    else:
        endpoint = "videos"
        params.update(chart="mostPopular", regionCode="SK")
    try:
        with urlopen("https://www.googleapis.com/youtube/v3/" + endpoint + "?" + urlencode(params), timeout=12) as response:
            items = json.load(response)["items"]
        return jsonify([dict(title=i["snippet"]["title"], video=i["id"]["videoId"] if channel else i["id"]) for i in items])
    except (OSError, ValueError, KeyError):
        return jsonify(error="YouTube neodpovedal. Skontroluj prístup, kľúč a kvótu."), 502
