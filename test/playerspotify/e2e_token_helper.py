#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Credential helper for the real-Spotify e2e tests (test_e2e_real_spotify.py)

Modes:

  --bootstrap
      One-time, interactive. Prints the Spotify authorisation URL; after
      approving in a browser, paste the redirect URL back. Prints the
      REFRESH TOKEN to store as the SPOTIFY_E2E_REFRESH_TOKEN secret.
      Needs SPOTIFY_E2E_CLIENT_ID / SPOTIFY_E2E_CLIENT_SECRET in the
      environment (or interactive prompts).

  --print-access-token
      Non-interactive (CI). Exchanges SPOTIFY_E2E_REFRESH_TOKEN for a fresh
      access token and prints it — used to log a headless librespot into
      the account via `librespot --access-token`.

  --wait-device NAME [--timeout SECONDS]
      Non-interactive (CI). Polls the account's Connect device list until
      NAME appears (librespot needs a moment to register after starting).

Requires: pip install spotipy
"""

import argparse
import os
import sys
import time
from urllib.parse import urlparse, parse_qs

# Must match PlayerSpotify._scope (see src/jukebox/components/playerspotify)
SCOPE = ('user-read-playback-state '
         'user-modify-playback-state '
         'user-read-currently-playing '
         'streaming')
DEFAULT_REDIRECT_URI = 'http://127.0.0.1:8888/callback'


def _require_env(name, prompt=None):
    value = os.environ.get(name, '')
    if not value and prompt:
        value = input(f'{prompt}: ').strip()
    if not value:
        sys.exit(f'ERROR: {name} is not set')
    return value


def _oauth_manager(interactive=False):
    from spotipy.oauth2 import SpotifyOAuth
    prompts = ('Spotify app Client ID', 'Spotify app Client Secret') if interactive else (None, None)
    return SpotifyOAuth(
        client_id=_require_env('SPOTIFY_E2E_CLIENT_ID', prompts[0]),
        client_secret=_require_env('SPOTIFY_E2E_CLIENT_SECRET', prompts[1]),
        redirect_uri=os.environ.get('SPOTIFY_E2E_REDIRECT_URI', DEFAULT_REDIRECT_URI),
        scope=SCOPE,
        open_browser=False,
        cache_path=None,
    )


def bootstrap():
    auth = _oauth_manager(interactive=True)
    print('\n1. Open this URL in a browser and approve access:\n')
    print(f'   {auth.get_authorize_url()}\n')
    print('2. The browser lands on the Redirect URI (an error page is fine).')
    pasted = input('3. Paste the full redirect URL (or just the code) here: ').strip()

    code = pasted
    if '://' in pasted or '?' in pasted:
        query = urlparse(pasted).query or pasted.split('?', 1)[-1]
        code = (parse_qs(query).get('code') or [''])[0]
    if not code:
        sys.exit('ERROR: no authorisation code found in the pasted input')

    token_info = auth.get_access_token(code, as_dict=True, check_cache=False)
    refresh_token = token_info.get('refresh_token', '')
    if not refresh_token:
        sys.exit('ERROR: Spotify did not return a refresh token')
    print('\nStore this as the SPOTIFY_E2E_REFRESH_TOKEN secret '
          '(GitHub: Settings -> Secrets and variables -> Actions):\n')
    print(refresh_token)


def print_access_token():
    auth = _oauth_manager()
    refresh_token = _require_env('SPOTIFY_E2E_REFRESH_TOKEN')
    token_info = auth.refresh_access_token(refresh_token)
    print(token_info['access_token'])


def wait_device(name, timeout):
    import spotipy
    auth = _oauth_manager()
    refresh_token = _require_env('SPOTIFY_E2E_REFRESH_TOKEN')
    token_info = auth.refresh_access_token(refresh_token)
    client = spotipy.Spotify(auth=token_info['access_token'])

    wanted = name.strip().casefold()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        devices = client.devices().get('devices', [])
        names = [(device.get('name') or '').strip().casefold() for device in devices]
        if wanted in names:
            print(f"Connect device '{name}' is online.")
            return
        time.sleep(3)
    sys.exit(f"ERROR: Connect device '{name}' did not appear within {timeout}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--bootstrap', action='store_true')
    group.add_argument('--print-access-token', action='store_true')
    group.add_argument('--wait-device', metavar='NAME')
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()

    if args.bootstrap:
        bootstrap()
    elif args.print_access_token:
        print_access_token()
    else:
        wait_device(args.wait_device, args.timeout)


if __name__ == '__main__':
    main()
