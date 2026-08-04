# -*- coding: utf-8 -*-
"""Shared harness for hardware-free Spotify integration tests

Boots the *real* code — ``PlayerSpotify`` (full constructor), the real
player arbiter (components.player), the real NvManager, device_resolver,
auth_code and librespot_seeder modules — and fakes only the true
boundaries:

* the Spotify Web API      -> :class:`fake_spotify.FakeSpotify`
* OAuth                    -> :class:`fake_spotify.FakeSpotifyOAuth`
* wall-clock time          -> :class:`fake_spotify.FakeClock`
* the YAML config handler  -> :class:`InMemoryConfig`
* the ZMQ publisher        -> :class:`RecordingPublisher`
* the status poll timer    -> :class:`FakeEndlessTimer` (tests tick manually)

Everything is deterministic and in-process: no Raspberry Pi, no network,
no sleeping, no background polling.
"""

import importlib.util
import itertools
import json
import os
import sys
import types
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parents[1] / 'src' / 'jukebox'
_ENV_COUNTER = itertools.count()

# Must match PlayerSpotify._scope — a cached token with a narrower scope is
# rejected by spotipy and the plugin would fall back to the OAuth flow.
PLUGIN_OAUTH_SCOPE = ('user-read-playback-state '
                      'user-modify-playback-state '
                      'user-read-currently-playing '
                      'streaming')

E2E_REQUIRED_ENV = ('SPOTIFY_E2E_CLIENT_ID',
                    'SPOTIFY_E2E_CLIENT_SECRET',
                    'SPOTIFY_E2E_REFRESH_TOKEN')


def _load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fake_spotify = _load_module_from_path('fake_spotify', _HERE / 'fake_spotify.py')


class InMemoryConfig:
    """Minimal stand-in for jukebox.cfghandler's config handler"""

    def __init__(self, data=None):
        self._data = data or {}

    def getn(self, *keys, default=None):
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def setn(self, *keys, value=None):
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def setndefault(self, *keys, value=None):
        missing = object()
        existing = self.getn(*keys, default=missing)
        if existing is missing:
            self.setn(*keys, value=value)
            return value
        return existing

    def save(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class RecordingPublisher:
    """Captures everything the plugin publishes on the ZMQ topics"""

    def __init__(self):
        self.messages = []

    def send(self, topic, payload):
        self.messages.append((topic, payload))


class FakeEndlessTimer:
    """Replaces GenericEndlessTimerClass; tests trigger ticks explicitly"""

    def __init__(self, name, interval, function):
        self.name = name
        self.interval = interval
        self.function = function
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def tick(self):
        self.function()


def _identity_decorator(function):
    return function


class SpotifyEnv:
    """One fully wired jukebox-Spotify environment for a single test

    Attributes tests use most:
      player       the real PlayerSpotify instance
      spotify      the FakeSpotify account/API emulator
      clock        FakeClock (advance() to move playback forward)
      arbiter      the real PlayerArbiter from components.player
      publisher    RecordingPublisher with every published message
      status_timer FakeEndlessTimer of the status poll (tick() to poll)
    """

    def __init__(self, tmp_path, config_overrides=None, real_spotify=False):
        env_id = next(_ENV_COUNTER)
        self._package_name = f'playerspotify_integration_{env_id}'
        self.real_spotify = real_spotify

        self.clock = fake_spotify.FakeClock()
        self.spotify = None if real_spotify else fake_spotify.FakeSpotify(self.clock)
        self.publisher = RecordingPublisher()

        config = {
            'client_id': 'test-client-id',
            'client_secret': 'test-client-secret',
            'redirect_uri': 'http://127.0.0.1:8888/callback',
            'token_cache': str(tmp_path / f'spotify_token_{env_id}.cache'),
            'status_file': str(tmp_path / f'spotify_status_{env_id}.json'),
            'device_name': 'Phoniebox',
            'librespot': {'auto_login': False},
        }
        if real_spotify:
            config.update({
                'client_id': os.environ['SPOTIFY_E2E_CLIENT_ID'],
                'client_secret': os.environ['SPOTIFY_E2E_CLIENT_SECRET'],
                'device_name': os.environ.get('SPOTIFY_E2E_DEVICE_NAME', 'Phoniebox'),
            })
            self._seed_token_cache(config['token_cache'])
        config.update(config_overrides or {})
        self.cfg = InMemoryConfig({'playerspotify': config})

        self._previous_modules = {}
        self._install_modules()
        try:
            self.module = self._load_plugin_module()
            self.arbiter = self.module.components.player.arbiter
            self.player = self.module.PlayerSpotify()
        except BaseException:
            self._restore_modules()
            raise
        self.status_timer = self._timers[0]
        if real_spotify:
            # Expose the real spotipy client under the same attribute the
            # fake occupies in emulator mode
            self.spotify = self.player._sp

    @staticmethod
    def _seed_token_cache(cache_path):
        """Pre-seed a spotipy token cache from SPOTIFY_E2E_REFRESH_TOKEN

        The access token is left empty and expired, so the very first API
        call exercises the plugin's real refresh path.
        """
        with open(cache_path, 'w') as cache_file:
            json.dump({
                'access_token': '',
                'token_type': 'Bearer',
                'expires_in': 0,
                'expires_at': 0,
                'refresh_token': os.environ['SPOTIFY_E2E_REFRESH_TOKEN'],
                'scope': PLUGIN_OAUTH_SCOPE,
            }, cache_file)

    # -- module wiring ---------------------------------------------------

    def _install_modules(self):
        env = self

        # Stub packages whose __path__ points at the real source tree:
        # non-stubbed submodules (components.player, jukebox.NvManager)
        # resolve to the real implementations.
        components = types.ModuleType('components')
        components.__path__ = [str(_SRC / 'components')]

        jukebox = types.ModuleType('jukebox')
        jukebox.__path__ = [str(_SRC / 'jukebox')]

        cfghandler = types.ModuleType('jukebox.cfghandler')
        cfghandler.get_handler = lambda _name: env.cfg

        plugs = types.ModuleType('jukebox.plugs')
        plugs.tag = _identity_decorator
        plugs.initialize = _identity_decorator
        plugs.atexit = _identity_decorator
        plugs.register = lambda *args, **kwargs: None

        self._timers = []

        class _RecordingTimer(FakeEndlessTimer):
            def __init__(self, name, interval, function):
                super().__init__(name, interval, function)
                env._timers.append(self)

        multitimer = types.ModuleType('jukebox.multitimer')
        multitimer.GenericEndlessTimerClass = _RecordingTimer

        publishing = types.ModuleType('jukebox.publishing')
        publishing.get_publisher = lambda: env.publisher

        jukebox.cfghandler = cfghandler
        jukebox.plugs = plugs
        jukebox.multitimer = multitimer
        jukebox.publishing = publishing

        stubs = {
            'components': components,
            'jukebox': jukebox,
            'jukebox.cfghandler': cfghandler,
            'jukebox.plugs': plugs,
            'jukebox.multitimer': multitimer,
            'jukebox.publishing': publishing,
        }
        if not self.real_spotify:
            spotipy = types.ModuleType('spotipy')
            oauth2 = types.ModuleType('spotipy.oauth2')
            spotipy.Spotify = lambda auth_manager=None: env.spotify
            oauth2.SpotifyOAuth = fake_spotify.FakeSpotifyOAuth
            spotipy.oauth2 = oauth2
            stubs['spotipy'] = spotipy
            stubs['spotipy.oauth2'] = oauth2
        # Names that must import fresh (real modules) inside this environment
        fresh = ['components.player', 'jukebox.NvManager']
        touched = list(stubs) + fresh + [
            self._package_name,
            f'{self._package_name}.librespot_seeder',
            f'{self._package_name}.auth_code',
            f'{self._package_name}.device_resolver',
        ]
        self._previous_modules = {name: sys.modules.get(name) for name in touched}
        for name in fresh:
            sys.modules.pop(name, None)
        sys.modules.update(stubs)

    def _load_plugin_module(self):
        module_path = _SRC / 'components' / 'playerspotify' / '__init__.py'
        spec = importlib.util.spec_from_file_location(
            self._package_name, module_path,
            submodule_search_locations=[str(module_path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[self._package_name] = module
        spec.loader.exec_module(module)
        if not self.real_spotify:
            # The transfer/retry path sleeps; advance the fake clock instead
            module.time = types.SimpleNamespace(sleep=self.clock.sleep)
        return module

    def _restore_modules(self):
        for name, module in self._previous_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        self._previous_modules = {}

    def close(self):
        try:
            self.player.exit()
        finally:
            self._restore_modules()

    # -- helpers for tests -------------------------------------------------

    def poll(self):
        """One tick of the status poll timer (normally every 2 s)"""
        self.status_timer.tick()

    def statuses(self):
        """All published 'playerstatus' payloads, oldest first"""
        return [payload for topic, payload in self.publisher.messages
                if topic == 'playerstatus']

    def last_status(self):
        return self.statuses()[-1]

    def clear_published(self):
        self.publisher.messages.clear()


def _spotify_id(seed):
    """Deterministic 22-character Spotify-shaped object id"""
    return (seed + '0' * 22)[:22]


PHONIEBOX_DEVICE_ID = 'phoniebox-librespot-device'


def _populate_standard_account(env):
    spotify = env.spotify
    spotify.add_device(PHONIEBOX_DEVICE_ID, 'Phoniebox')
    track_1 = _spotify_id('TrackOne')
    track_2 = _spotify_id('TrackTwo')
    track_3 = _spotify_id('TrackThree')
    env.track1_uri = spotify.add_track(
        track_1, name='First Song', artists=('Alpha Artist',), duration_s=180,
        album_name='Album A', image_url='https://i.scdn.co/image/first')
    env.track2_uri = spotify.add_track(
        track_2, name='Second Song', artists=('Beta Artist',), duration_s=240,
        album_name='Album B', image_url='https://i.scdn.co/image/second')
    env.track3_uri = spotify.add_track(
        track_3, name='Third Song', artists=('Gamma Artist',), duration_s=200,
        album_name='Album C', image_url='https://i.scdn.co/image/third')
    env.playlist_uri = spotify.add_playlist(
        _spotify_id('BedtimePlaylist'), 'Bedtime Songs',
        [track_1, track_2, track_3])
    env.album_uri = spotify.add_album(
        _spotify_id('GreatestAlbum'), 'Greatest Hits', [track_1, track_2],
        artists=('Alpha Artist',))
    env.device_id = PHONIEBOX_DEVICE_ID
    env.track_ids = [track_1, track_2, track_3]


@pytest.fixture
def make_spotify_env(tmp_path):
    """Factory for fully wired Spotify environments (see SpotifyEnv)"""
    environments = []

    def _make(config_overrides=None, standard_account=True):
        env = SpotifyEnv(tmp_path, config_overrides)
        if standard_account:
            _populate_standard_account(env)
        environments.append(env)
        return env

    yield _make
    for env in reversed(environments):
        env.close()


@pytest.fixture
def spotify_env(make_spotify_env):
    """Default environment: authenticated account, 'Phoniebox' device,
    three tracks, a playlist and an album."""
    return make_spotify_env()


@pytest.fixture
def real_spotify_env(tmp_path):
    """Environment against the REAL Spotify Web API (opt-in)

    Skips unless spotipy is installed and the SPOTIFY_E2E_* credentials are
    present in the environment. See the 'Automated testing' section in
    documentation/developers/spotify-integration.md for setup.
    """
    try:
        import spotipy  # noqa: F401
    except ImportError:
        pytest.skip('spotipy is not installed')
    missing = [name for name in E2E_REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        pytest.skip('Spotify e2e credentials not set: ' + ', '.join(missing))

    env = SpotifyEnv(tmp_path, real_spotify=True)
    try:
        yield env
    finally:
        env.close()
