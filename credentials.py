"""Keep active credentials in memory; use macOS Keychain on request."""
import os
import sys

from flask import Blueprint, jsonify, request

settings = Blueprint("settings", __name__)
providers = {"openai": "OPENAI_API_KEY", "youtube": "YOUTUBE_API_KEY"}
session_keys = {}
sources = {}

if sys.platform == "darwin":
    from keyring.backends.macOS import Keyring
    storage = Keyring()
else:
    storage = None


class KeychainUnavailable(Exception):
    pass


@settings.app_errorhandler(KeychainUnavailable)
def unavailable(_error):
    return jsonify(error="Kľúčenka nepovolila prístup. Vlož kľúč v Nastaveniach a klikni na Použiť pre túto reláciu."), 409


def credential(provider):
    if provider in session_keys:
        return session_keys[provider]
    if storage is not None:
        try:
            value = storage.get_password("CLIPRO", provider)
        except Exception:
            raise KeychainUnavailable() from None
        if value:
            session_keys[provider] = value
            sources[provider] = "keychain"
            return value
    return os.getenv(providers[provider], "")


@settings.get("/api/settings")
def status():
    # Listing settings must never unlock either Keychain item.
    states = {}
    for p in providers:
        states[p] = sources.get(p) or ("env" if os.getenv(providers[p]) else
                                        "unread" if storage is not None else "missing")
    return jsonify(states=states, keychain=storage is not None)


def activate(provider, value, source="session"):
    session_keys[provider] = value
    sources[provider] = source


@settings.post("/api/settings/<provider>")
def update(provider):
    if provider not in providers:
        return jsonify(error="Neznáma služba."), 404
    data = request.get_json()
    value = data.get("key") if isinstance(data, dict) else None
    if not isinstance(value, str):
        return jsonify(error="Skontroluj formát kľúča."), 400
    value = value.strip()
    if value and (not value.isascii() or not value.isprintable() or any(c.isspace() for c in value)):
        return jsonify(error="Kľúč obsahuje medzeru alebo neplatný znak."), 400
    persist = storage is not None and data.get("remember", True)
    try:
        if value and persist:
            storage.set_password("CLIPRO", provider, value)
        elif not value and storage is not None and storage.get_password("CLIPRO", provider):
            storage.delete_password("CLIPRO", provider)
    except Exception:
        raise KeychainUnavailable() from None
    if value:
        activate(provider, value, "keychain" if persist else "session")
    else:
        session_keys.pop(provider, None)
        sources[provider] = "env" if os.getenv(providers[provider]) else "missing"
    return status()
