# -*- coding: utf-8 -*-
"""Log the local librespot instance into the Spotify account

librespot started via zeroconf is not tied to any account until a Spotify
client on the network 'activates' it once — that is the phone step this
module removes. librespot v0.5+ can instead log in directly with an OAuth
access token (``--access-token``) and then stores reusable credentials in
its cache, so it reconnects on its own at every boot.

The jukebox already obtains such a token through its web UI OAuth flow
(scope 'streaming' required), so it can seed librespot fully automatically.

Kept free of jukebox imports so it can be unit tested without the daemon
dependencies (spotipy, zmq, ...).
"""

import os
import shutil
import subprocess
import time

CREDENTIALS_FILENAME = 'credentials.json'


def find_librespot(binary: str = 'librespot'):
    """Return the full path of the librespot binary, or None if not installed"""
    return shutil.which(binary)


def credentials_path(cache_dir: str) -> str:
    """Return the path of librespot's reusable credentials file"""
    return os.path.join(os.path.expanduser(cache_dir), CREDENTIALS_FILENAME)


def has_cached_credentials(cache_dir: str) -> bool:
    """Return True if librespot already has reusable credentials cached"""
    return os.path.isfile(credentials_path(cache_dir))


def supports_access_token(librespot_bin: str, run=subprocess.run) -> bool:
    """Return True if the installed librespot supports --access-token (v0.5+)"""
    try:
        result = run([librespot_bin, '--help'], capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    return '--access-token' in (result.stdout or '') + (result.stderr or '')


def build_seed_command(librespot_bin: str, access_token: str, cache_dir: str,
                       device_name: str) -> list:
    """Build the one-shot librespot login command

    The pipe backend avoids touching the audio system and discovery is
    disabled so the seed run does not clash with the regular librespot
    service that may be running at the same time.
    """
    return [librespot_bin,
            '--name', device_name,
            '--access-token', access_token,
            '--cache', os.path.expanduser(cache_dir),
            '--backend', 'pipe',
            '--disable-discovery']


def seed(librespot_bin: str, access_token: str, cache_dir: str, device_name: str,
         timeout: float = 20.0, poll_interval: float = 0.5,
         popen=subprocess.Popen) -> bool:
    """Run librespot once with the access token until reusable credentials exist

    :return: True if the credentials file was written (login succeeded)
    """
    cred_file = credentials_path(cache_dir)
    os.makedirs(os.path.dirname(cred_file), exist_ok=True)
    cmd = build_seed_command(librespot_bin, access_token, cache_dir, device_name)
    proc = popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if os.path.isfile(cred_file):
                return True
            if proc.poll() is not None:
                # librespot exited (e.g. bad token) - no point in waiting on
                break
            time.sleep(poll_interval)
        return os.path.isfile(cred_file)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
