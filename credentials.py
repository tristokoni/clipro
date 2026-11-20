"""Local credentials for the two integrations used by CLIPRO."""
import os
import sys

from flask import Blueprint, jsonify, request

settings = Blueprint("settings", __name__)
providers = {"openai": "OPENAI_API_KEY", "youtube": "YOUTUBE_API_KEY"}
session_keys = {}

if sys.platform == "darwin":
    from keyring.backends.macOS import Keyring
    storage = Keyring()
else:
    storage = None


def stored(provider):
    if storage is not None:
        return storage.get_password("CLIPRO", provider)
    return session_keys.get(provider)


def credential(provider):
    return stored(provider) or os.getenv(providers[provider], "")


@settings.get("/api/settings")
def status():
    return jsonify(keys={p: bool(credential(p)) for p in providers},
                   keychain=storage is not None)


@settings.post("/api/settings/<provider>")
def update(provider):
    if provider not in providers:
        return jsonify(error="Neznáma služba."), 404
    data = request.get_json()
    value = data.get("key") if isinstance(data, dict) else None
    if not isinstance(value, str) or (value and not (value.isascii() and value.isprintable())):
        return jsonify(error="Skontroluj formát kľúča."), 400
    value = value.strip()
    if storage is None:
        session_keys[provider] = value
    elif value:
        storage.set_password("CLIPRO", provider, value)
    elif stored(provider):
        storage.delete_password("CLIPRO", provider)
    return status()
