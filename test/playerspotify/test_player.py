import importlib.util
import pathlib
import sys
import threading
import types
from unittest.mock import Mock, call, patch

import pytest


def _identity_decorator(function):
    return function


def _load_player_module():
    """Load the player without importing the daemon or starting its services."""
    components = types.ModuleType('components')
    components.__path__ = []
    player = types.ModuleType('components.player')
    player.arbiter = Mock()
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
    publishing.get_publisher = Mock(return_value=Mock())
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


def test_status_poll_does_not_publish_when_spotify_is_inactive():
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._build_status = Mock(return_value={'state': 'play'})
    player_module.components.player.arbiter.is_active.return_value = False
    publisher = player_module.publishing.get_publisher.return_value
    publisher.reset_mock()
    player_module.publishing.get_publisher.reset_mock()

    player._status_poll()

    player._build_status.assert_not_called()
    player_module.publishing.get_publisher.assert_not_called()
    publisher.send.assert_not_called()


def test_status_poll_publishes_once_when_spotify_is_active():
    status = {'player': 'spotify', 'state': 'play'}
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._build_status = Mock(return_value=status)
    player_module.components.player.arbiter.is_active.return_value = True
    publisher = player_module.publishing.get_publisher.return_value
    publisher.reset_mock()
    player_module.publishing.get_publisher.reset_mock()

    player._status_poll()

    player._build_status.assert_called_once_with()
    player_module.publishing.get_publisher.assert_called_once_with()
    publisher.send.assert_called_once_with('playerstatus', status)


def _device_error(status, message='Device not found'):
    error = RuntimeError(message)
    error.http_status = status
    return error


def _player_for_start_playback(devices):
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._sp = Mock()
    player._playback_device = Mock(side_effect=devices)
    return player


def test_start_playback_succeeds_without_transfer():
    player = _player_for_start_playback(['device-id'])

    player._start_playback(context_uri='spotify:playlist:test')

    player._sp.start_playback.assert_called_once_with(
        device_id='device-id', context_uri='spotify:playlist:test')
    player._sp.transfer_playback.assert_not_called()


def test_start_playback_retries_a_refreshed_device_without_transfer():
    player = _player_for_start_playback(['stale-id', 'fresh-id'])
    player._sp.start_playback.side_effect = [RuntimeError('stale'), None]

    player._start_playback(uris=['spotify:track:test'])

    assert player._sp.start_playback.call_args_list == [
        call(device_id='stale-id', uris=['spotify:track:test']),
        call(device_id='fresh-id', uris=['spotify:track:test']),
    ]
    player._sp.transfer_playback.assert_not_called()


def test_start_playback_activates_visible_device_after_device_not_found():
    player = _player_for_start_playback(['device-id', 'device-id'])
    player._sp.start_playback.side_effect = [_device_error(404), None]

    with patch.object(player_module.time, 'sleep') as sleep:
        player._start_playback(context_uri='spotify:playlist:test')

    player._sp.transfer_playback.assert_called_once_with(
        device_id='device-id', force_play=False)
    sleep.assert_called_once_with(2)
    assert player._sp.start_playback.call_args_list == [
        call(device_id='device-id', context_uri='spotify:playlist:test'),
        call(device_id='device-id', context_uri='spotify:playlist:test'),
    ]


def test_start_playback_does_not_transfer_for_other_errors():
    player = _player_for_start_playback(['device-id', 'device-id'])
    player._sp.start_playback.side_effect = _device_error(403)

    with pytest.raises(RuntimeError, match='Device not found'):
        player._start_playback(context_uri='spotify:playlist:test')

    player._sp.transfer_playback.assert_not_called()


def test_start_playback_retries_device_transfer_after_device_not_found():
    player = _player_for_start_playback(
        ['device-id', 'device-id', 'refreshed-id'])
    player._sp.start_playback.side_effect = [_device_error(404), None]
    player._sp.transfer_playback.side_effect = [_device_error(404), None]

    with patch.object(player_module.time, 'sleep') as sleep:
        player._start_playback(context_uri='spotify:playlist:test')

    assert player._sp.transfer_playback.call_args_list == [
        call(device_id='device-id', force_play=False),
        call(device_id='refreshed-id', force_play=False),
    ]
    assert sleep.call_args_list == [call(2), call(2)]
    assert player._sp.start_playback.call_args_list == [
        call(device_id='device-id', context_uri='spotify:playlist:test'),
        call(device_id='refreshed-id', context_uri='spotify:playlist:test'),
    ]
