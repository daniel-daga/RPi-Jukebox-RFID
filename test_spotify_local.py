"""
Standalone Spotify API smoke test — no jukebox daemon needed.

Reads credentials from a .env file in the same directory:
    SPOTIFY_CLIENT_ID=...
    SPOTIFY_CLIENT_SECRET=...

Make sure http://localhost:8888/callback is listed as a Redirect URI in your Spotify app.
Run:  py test_spotify_local.py
A browser will open for OAuth on the first run; the token is cached in .spotify_token_test
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def _load_env(path=".env"):
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing"
)


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Fill in CLIENT_ID and CLIENT_SECRET at the top of this file.")
        return

    print(f"Using redirect URI: {REDIRECT_URI}")
    print("Authenticating with Spotify...")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=".spotify_token_test",
            open_browser=True,
        )
    )

    # ── Account info ──────────────────────────────────────────────────────────
    me = sp.me()
    print(f"\nLogged in as: {me.get('display_name') or me.get('id')} ({me.get('email', 'no email')})")

    # ── Available devices ─────────────────────────────────────────────────────
    print("\nAvailable Spotify Connect devices:")
    devices = sp.devices().get("devices", [])
    if not devices:
        print("  (none — open Spotify on any device and re-run)")
    for d in devices:
        active = " [ACTIVE]" if d.get("is_active") else ""
        print(f"  {d['name']} ({d['type']})  id={d['id']}{active}")

    # ── Current playback ──────────────────────────────────────────────────────
    print("\nCurrent playback:")
    current = sp.current_playback()
    if not current:
        print("  Nothing playing")
    else:
        item = current.get("item") or {}
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        state = "playing" if current.get("is_playing") else "paused"
        print(f"  {state}: {item.get('name')} — {artists}")
        print(f"  URI: {item.get('uri')}")

    # ── Play a test URI ───────────────────────────────────────────────────────
    if devices:
        test_uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"  # Today's Top Hits
        answer = input(f"\nStart playing '{test_uri}' on the active device? [y/N] ").strip().lower()
        if answer == "y":
            try:
                sp.start_playback(context_uri=test_uri)
                print("  Playback started.")
            except spotipy.exceptions.SpotifyException as e:
                print(f"  ERROR: {e}")
    else:
        print("\nSkipping playback test — no devices available.")

    print("\nDone. Token cached in .spotify_token_test for subsequent runs.")


if __name__ == "__main__":
    main()
