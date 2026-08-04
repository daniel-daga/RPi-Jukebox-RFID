# -*- coding: utf-8 -*-
"""Opt-in end-to-end tests against the REAL Spotify Web API

These run the real PlayerSpotify plugin against Spotify's servers — the
only test layer that can catch changes in Spotify's actual behaviour
(auth, rate limits, Connect device semantics). They are skipped unless
credentials are configured, so plain `pytest` stays hardware- and
network-free.

Required environment (see documentation/developers/spotify-integration.md):
    SPOTIFY_E2E_CLIENT_ID       Spotify Developer App client id
    SPOTIFY_E2E_CLIENT_SECRET   Spotify Developer App client secret
    SPOTIFY_E2E_REFRESH_TOKEN   from e2e_token_helper.py --bootstrap

Optional:
    SPOTIFY_E2E_DEVICE_NAME     Connect device to play on (e.g. a headless
                                librespot in CI, or a real Phoniebox)
    SPOTIFY_E2E_ALLOW_PLAYBACK  '1' enables tests that actually start
                                playback on the account
    SPOTIFY_E2E_PLAYLIST_ID     a playlist owned by the test account
    SPOTIFY_E2E_TRACK_URI       track for playback tests (default below)

Use a dedicated Spotify Premium test account: playback tests really play.
"""

import os
import time

import pytest

pytestmark = pytest.mark.e2e_spotify

# Content ids from Spotify's own Web API documentation examples — stable,
# globally available, and safe for metadata assertions.
DOCS_TRACK_ID = '11dFghVXANMlKmJXsNCbNl'    # Cut To The Feeling
DOCS_ALBUM_ID = '4aawyAB9vmqN3uQ7FjRGTy'    # Global Warming
DEFAULT_PLAYBACK_URI = f'spotify:track:{DOCS_TRACK_ID}'


def wait_until(condition, timeout=30, interval=1.0):
    """Poll until condition() is truthy; the real API is eventually consistent."""
    deadline = time.monotonic() + timeout
    result = condition()
    while not result and time.monotonic() < deadline:
        time.sleep(interval)
        result = condition()
    return result


def _require_device_name():
    device_name = os.environ.get('SPOTIFY_E2E_DEVICE_NAME')
    if not device_name:
        pytest.skip('SPOTIFY_E2E_DEVICE_NAME not set - no Connect device to test against')
    return device_name


def _require_playback_opt_in():
    if os.environ.get('SPOTIFY_E2E_ALLOW_PLAYBACK') != '1':
        pytest.skip('playback e2e disabled - set SPOTIFY_E2E_ALLOW_PLAYBACK=1 to enable')


def _polled_status(env):
    """Trigger one status poll and return the freshly published payload"""
    env.poll()
    statuses = env.statuses()
    return statuses[-1] if statuses else {}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_refresh_token_authenticates_the_plugin(real_spotify_env):
    env = real_spotify_env

    status = env.player.get_auth_status()

    assert status['configured'] is True
    assert status['authenticated'] is True
    assert status['auth_in_progress'] is False
    # Account lookup went through the real Web API
    assert status.get('user')


# ---------------------------------------------------------------------------
# Metadata (read-only, no device needed)
# ---------------------------------------------------------------------------


def test_resolve_source_fetches_real_track_metadata(real_spotify_env):
    env = real_spotify_env

    result = env.player.resolve_source(
        f'https://open.spotify.com/track/{DOCS_TRACK_ID}?si=share-token')

    assert result.get('error') is None, result
    assert result['type'] == 'track'
    assert result['uri'] == f'spotify:track:{DOCS_TRACK_ID}'
    assert result['name']
    assert result['subtitle']
    assert result['image_url'].startswith('https://')


def test_resolve_source_fetches_real_album_metadata(real_spotify_env):
    env = real_spotify_env

    result = env.player.resolve_source(f'spotify:album:{DOCS_ALBUM_ID}')

    assert result.get('error') is None, result
    assert result['type'] == 'album'
    assert result['name']
    assert result['image_url'].startswith('https://')


def test_resolve_source_fetches_own_playlist_metadata(real_spotify_env):
    # Spotify-owned editorial playlists are no longer readable by newer dev
    # apps (API change of Nov 2024), so this needs a playlist owned by the
    # test account itself.
    playlist_id = os.environ.get('SPOTIFY_E2E_PLAYLIST_ID')
    if not playlist_id:
        pytest.skip('SPOTIFY_E2E_PLAYLIST_ID not set')
    env = real_spotify_env

    result = env.player.resolve_source(f'spotify:playlist:{playlist_id}')

    assert result.get('error') is None, result
    assert result['type'] == 'playlist'
    assert result['name']


def test_resolve_source_reports_unknown_content_as_error(real_spotify_env):
    env = real_spotify_env

    result = env.player.resolve_source('spotify:track:' + 'Z' * 22)

    # Depending on how Spotify rejects the id this maps to either code;
    # both are safe, stable errors for the web UI.
    assert result.get('error') in ('not_found', 'spotify_unavailable')


# ---------------------------------------------------------------------------
# Spotify Connect device (headless librespot in CI, or a real Phoniebox)
# ---------------------------------------------------------------------------


def test_configured_connect_device_is_visible(real_spotify_env):
    device_name = _require_device_name()
    env = real_spotify_env

    def device_listed():
        names = [(device.get('name') or '').strip().casefold()
                 for device in env.player.list_devices()]
        return device_name.strip().casefold() in names

    assert wait_until(device_listed, timeout=60, interval=3), (
        f"Connect device '{device_name}' not visible on the account - "
        'is librespot running and logged in?')


def test_play_pause_seek_cycle_on_real_device(real_spotify_env):
    device_name = _require_device_name()
    _require_playback_opt_in()
    env = real_spotify_env
    track_uri = os.environ.get('SPOTIFY_E2E_TRACK_URI', DEFAULT_PLAYBACK_URI)

    try:
        # First swipe: playback starts on the configured device
        env.player.play_card(track_uri)
        assert wait_until(
            lambda: _polled_status(env).get('state') == 'play'
            and _polled_status(env).get('file') == track_uri
        ), f'track did not start playing on {device_name}'

        # Second swipe: default action toggles to pause
        env.player.play_card(track_uri)
        assert wait_until(
            lambda: _polled_status(env).get('state') == 'pause'
        ), 'second swipe did not pause playback'

        # Seek while paused, then resume via third swipe
        env.player.seek(30)
        env.player.play_card(track_uri)
        assert wait_until(
            lambda: _polled_status(env).get('state') == 'play'
            and float(_polled_status(env).get('elapsed', 0)) >= 29
        ), 'resume after seek did not continue from the seek position'
    finally:
        try:
            env.spotify.pause_playback()
        except Exception:
            pass
