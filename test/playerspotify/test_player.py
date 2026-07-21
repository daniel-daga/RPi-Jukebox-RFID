import importlib.util
import pathlib
import sys
import threading
import types
from unittest.mock import Mock


def _identity_decorator(function):
    return function


def _load_player_module():
    """Load the player without importing the daemon or starting its services."""
    components = types.ModuleType('components')
    components.__path__ = []
    player = types.ModuleType('components.player')
    components.player = player

    jukebox = types.ModuleType('jukebox')
    jukebox.__path__ = []
    cfghandler = types.ModuleType('jukebox.cfghandler')
    cfghandler.get_handler = Mock(return_value=Mock())
    plugs = types.ModuleType('jukebox.plugs')
    plugs.tag = _identity_decorator
    plugs.initialize = _identity_decorator
    plugs.atexit = _identity_decorator
    multitimer = types.ModuleType('jukebox.multitimer')
    publishing = types.ModuleType('jukebox.publishing')
    nvmanager = types.ModuleType('jukebox.NvManager')
    nvmanager.nv_manager = Mock()
    jukebox.cfghandler = cfghandler
    jukebox.plugs = plugs
    jukebox.multitimer = multitimer
    jukebox.publishing = publishing

    package_name = 'playerspotify_under_test'
    librespot_seeder = types.ModuleType(f'{package_name}.librespot_seeder')
    auth_code = types.ModuleType(f'{package_name}.auth_code')
    auth_code.extract_auth_code = Mock()
    device_resolver = types.ModuleType(f'{package_name}.device_resolver')
    device_resolver.resolve_device_id = Mock()

    stubs = {
        'components': components,
        'components.player': player,
        'jukebox': jukebox,
        'jukebox.cfghandler': cfghandler,
        'jukebox.plugs': plugs,
        'jukebox.multitimer': multitimer,
        'jukebox.publishing': publishing,
        'jukebox.NvManager': nvmanager,
        f'{package_name}.librespot_seeder': librespot_seeder,
        f'{package_name}.auth_code': auth_code,
        f'{package_name}.device_resolver': device_resolver,
    }
    previous = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)

    module_path = (pathlib.Path(__file__).resolve().parents[2]
                   / 'src' / 'jukebox' / 'components' / 'playerspotify' / '__init__.py')
    spec = importlib.util.spec_from_file_location(
        package_name, module_path, submodule_search_locations=[str(module_path.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(package_name, None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
    return module


player_module = _load_player_module()
PlayerSpotify = player_module.PlayerSpotify


def _player_with_playback(playback):
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._lock = threading.RLock()
    player._sp = Mock()
    if isinstance(playback, Exception):
        player._sp.current_playback.side_effect = playback
    else:
        player._sp.current_playback.return_value = playback
    return player


def test_build_status_normalizes_spotify_playback_and_albumart():
    player = _player_with_playback({
        'is_playing': True,
        'progress_ms': 12345,
        'shuffle_state': True,
        'repeat_state': 'track',
        'item': {
            'id': 'track-id',
            'uri': 'spotify:track:track-id',
            'name': 'Test Track',
            'artists': [{'name': 'First Artist'}, {'name': 'Second Artist'}],
            'duration_ms': 234567,
            'album': {
                'name': 'Test Album',
                'images': [{'url': 'https://i.scdn.co/image/cover'}],
            },
        },
    })

    assert player._build_status() == {
        'player': 'spotify',
        'state': 'play',
        'songid': 'track-id',
        'file': 'spotify:track:track-id',
        'title': 'Test Track',
        'artist': 'First Artist, Second Artist',
        'album': 'Test Album',
        'albumart': 'https://i.scdn.co/image/cover',
        'elapsed': '12.345',
        'duration': '234.567',
        'random': '1',
        'repeat': '1',
        'single': '1',
    }


def test_build_status_uses_first_valid_album_image():
    player = _player_with_playback({
        'item': {
            'album': {
                'images': [None, {}, {'url': ''}, {'url': None},
                           {'url': 'https://i.scdn.co/image/valid'},
                           {'url': 'https://i.scdn.co/image/later'}],
            },
        },
    })

    assert player._build_status()['albumart'] == 'https://i.scdn.co/image/valid'


def test_build_status_handles_missing_item_album_and_images():
    for playback in (
        {'item': None},
        {'item': {}},
        {'item': {'album': None}},
        {'item': {'album': {}}},
        {'item': {'album': {'images': None}}},
        {'item': {'album': {'images': 'not-a-list'}}},
    ):
        status = _player_with_playback(playback)._build_status()
        assert status['albumart'] == ''


def test_build_status_without_playback_clears_albumart():
    assert _player_with_playback(None)._build_status() == {
        'player': 'spotify',
        'state': 'stop',
        'albumart': '',
    }


def test_build_status_returns_none_on_transient_api_error():
    player = _player_with_playback(RuntimeError('temporary Spotify failure'))

    assert player._build_status() is None
