# -*- coding: utf-8 -*-
"""Extraction of the OAuth authorisation code from user-pasted input

Fallback for setups where the Spotify redirect cannot reach the jukebox
(e.g. the app's Redirect URI points to 127.0.0.1): after approving, the
user copies the address bar of the error page and pastes it into the
web UI. This module turns that pasted text back into the auth code.

Kept free of jukebox imports so it can be unit tested without the
daemon dependencies (spotipy, zmq, ...).
"""

from urllib.parse import urlparse, parse_qs


def extract_auth_code(text: str):
    """Return the Spotify authorisation code contained in :attr:`text`

    Accepts either the full redirect URL the browser landed on
    (``http.../callback?code=AQD...&state=...``), just its query string,
    or the bare code itself.

    :param text: pasted user input
    :return: the auth code, or None if none could be found
    """
    if not text:
        return None
    text = text.strip()
    if not text:
        return None

    # Full URL or bare query string containing 'code='
    if 'code=' in text:
        query = urlparse(text).query if '://' in text else text.lstrip('?')
        params = parse_qs(query)
        code = params.get('code', [None])[0]
        return code or None

    # A URL without a code parameter is not a valid code itself
    if '://' in text or '?' in text or '&' in text:
        return None

    # Assume the bare code was pasted
    return text
