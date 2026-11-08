"""Language of server messages (German / English).

The language is server-wide (one user, one local server): the page reports its chosen language via POST /api/lang,
and messages created afterwards use it. Initial value: environment variable KM_LANG ("de"/"en"),
otherwise the Windows UI language (German -> "de", everything else -> "en").
"""
from __future__ import annotations

import ctypes
import os

LANGS = ("de", "en")


def _initial() -> str:
    env = os.environ.get("KM_LANG", "").lower()
    if env in LANGS:
        return env
    try:
        # primary language id 0x07 = German
        return "de" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x07 else "en"
    except Exception:
        return "en"


_lang = _initial()


def get_lang() -> str:
    return _lang


def set_lang(lang: str) -> str:
    global _lang
    if lang in LANGS:
        _lang = lang
    return _lang


def L(de: str, en: str) -> str:
    """Pick the text for the current language: L("Fehler", "Error")."""
    return en if _lang == "en" else de
