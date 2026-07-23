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
parse_spotify_source = player_module.parse_spotify_source


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


@pytest.mark.parametrize(('progress_ms', 'expected_elapsed'), [
    (-1, '0.0'),
    (999999, '10.0'),
])
def test_build_status_clamps_invalid_spotify_progress(progress_ms, expected_elapsed):
    player = _player_with_playback({
        'progress_ms': progress_ms,
        'item': {'duration_ms': 10000, 'album': {}},
    })

    status = player._build_status()

    assert status['elapsed'] == expected_elapsed
    assert status['duration'] == '10.0'


def test_build_status_advances_negative_spotify_progress_from_per_track_anchor():
    playback = {
        'progress_ms': -30000,
        'item': {
            'id': 'first-track',
            'uri': 'spotify:track:first-track',
            'duration_ms': 100000,
            'album': {},
        },
    }
    player = _player_with_playback(playback)

    assert player._build_status()['elapsed'] == '0.0'

    playback['progress_ms'] = -27000
    assert player._build_status()['elapsed'] == '3.0'

    playback['progress_ms'] = -50000
    playback['item']['id'] = 'second-track'
    playback['item']['uri'] = 'spotify:track:second-track'
    assert player._build_status()['elapsed'] == '0.0'


def test_build_status_reanchors_negative_progress_after_successful_seek():
    playback = {
        'progress_ms': -30000,
        'item': {
            'uri': 'spotify:track:test',
            'duration_ms': 100000,
            'album': {},
        },
    }
    player = _player_with_playback(playback)
    assert player._build_status()['elapsed'] == '0.0'

    player._pending_seek_ms = 60000
    playback['progress_ms'] = -29000
    assert player._build_status()['elapsed'] == '60.0'

    playback['progress_ms'] = -28000
    assert player._build_status()['elapsed'] == '61.0'


def test_build_status_persists_pause_override_while_spotify_reports_playing():
    playback = {
        'is_playing': True,
        'progress_ms': -30000,
        'item': {
            'uri': 'spotify:track:test',
            'duration_ms': 100000,
            'album': {},
        },
    }
    player = _player_with_playback(playback)
    assert player._build_status()['elapsed'] == '0.0'
    player._state_override = 'pause'
    player._frozen_progress_ms = player._last_normalized_progress_ms

    playback['progress_ms'] = -25000
    paused = player._build_status()
    assert paused['state'] == 'pause'
    assert paused['elapsed'] == '0.0'

    playback['progress_ms'] = -20000
    still_paused = player._build_status()
    assert still_paused['state'] == 'pause'
    assert still_paused['elapsed'] == '0.0'


def test_build_status_stops_at_duration_when_spotify_stays_playing():
    playback = {
        'is_playing': True,
        'progress_ms': -30000,
        'repeat_state': 'off',
        'item': {
            'uri': 'spotify:track:test',
            'duration_ms': 1000,
            'album': {},
        },
    }
    player = _player_with_playback(playback)
    assert player._build_status()['state'] == 'play'

    playback['progress_ms'] = -29000
    status = player._build_status()

    assert status['elapsed'] == '1.0'
    assert status['state'] == 'stop'
    assert player._state_override == 'stop'

    playback['progress_ms'] = -28000
    stopped = player._build_status()
    assert stopped['state'] == 'stop'
    assert stopped['elapsed'] == '1.0'


def test_build_status_clears_state_override_when_track_changes():
    playback = {
        'is_playing': True,
        'progress_ms': -30000,
        'item': {
            'uri': 'spotify:track:first',
            'duration_ms': 100000,
            'album': {},
        },
    }
    player = _player_with_playback(playback)
    player._state_override = 'pause'
    assert player._build_status()['state'] == 'pause'

    playback['item']['uri'] = 'spotify:track:second'
    playback['progress_ms'] = -50000

    assert player._build_status()['state'] == 'play'
    assert player._state_override is None
    assert player._frozen_progress_ms is None


def test_pause_uses_resolved_playback_device():
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._lock = threading.RLock()
    player._sp = Mock()
    player._playback_device = Mock(return_value='resolved-device-id')
    player._publish_status = Mock()

    player.pause()

    player._sp.pause_playback.assert_called_once_with(
        device_id='resolved-device-id')
    player._publish_status.assert_called_once_with(state_hint='pause')


def test_seek_uses_resolved_playback_device_and_converts_seconds_to_milliseconds():
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._lock = threading.RLock()
    player._sp = Mock()
    player._playback_device = Mock(return_value='resolved-device-id')
    player._publish_status = Mock()

    player.seek('60.125')

    player._sp.seek_track.assert_called_once_with(
        60125, device_id='resolved-device-id')
    assert player._pending_seek_ms == 60125
    player._publish_status.assert_called_once_with()


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


TRACK_ID = '11dFghVXANMlKmJXsNCbNl'
ALBUM_ID = '4aawyAB9vmqN3uQ7FjRGTy'
PLAYLIST_ID = '37i9dQZF1DXcBWIGoYBM5M'


@pytest.mark.parametrize(('value', 'source_type', 'source_id'), [
    (f'spotify:track:{TRACK_ID}', 'track', TRACK_ID),
    (f'spotify:album:{ALBUM_ID}', 'album', ALBUM_ID),
    (f'spotify:playlist:{PLAYLIST_ID}', 'playlist', PLAYLIST_ID),
    (f'https://open.spotify.com/track/{TRACK_ID}', 'track', TRACK_ID),
    (f'https://open.spotify.com/album/{ALBUM_ID}', 'album', ALBUM_ID),
    (f'https://open.spotify.com/playlist/{PLAYLIST_ID}', 'playlist', PLAYLIST_ID),
    (f'https://open.spotify.com/intl-de/track/{TRACK_ID}', 'track', TRACK_ID),
])
def test_parse_spotify_source_accepts_supported_uris_and_share_urls(
        value, source_type, source_id):
    assert parse_spotify_source(value) == {
        'uri': f'spotify:{source_type}:{source_id}',
        'external_url': f'https://open.spotify.com/{source_type}/{source_id}',
        'type': source_type,
        'id': source_id,
    }


def test_parse_spotify_source_strips_whitespace_query_and_fragment():
    assert parse_spotify_source(
        f'  https://open.spotify.com/track/{TRACK_ID}'
        '?si=share-token&utm_source=copy-link#ignored  '
    ) == {
        'uri': f'spotify:track:{TRACK_ID}',
        'external_url': f'https://open.spotify.com/track/{TRACK_ID}',
        'type': 'track',
        'id': TRACK_ID,
    }


@pytest.mark.parametrize('value', [
    None,
    123,
    '',
    '   ',
    'not Spotify',
    'spotify:track',
    'spotify:track:',
    f'spotify:track:{TRACK_ID}:extra',
    f'spotify:artist:{TRACK_ID}',
    f'spotify:episode:{TRACK_ID}',
    f'https://example.com/track/{TRACK_ID}',
    f'http://open.spotify.com/track/{TRACK_ID}',
    f'https://user:password@open.spotify.com/track/{TRACK_ID}',
    f'https://open.spotify.com:443/track/{TRACK_ID}',
    f'https://open.spotify.com/artist/{TRACK_ID}',
    f'https://open.spotify.com/episode/{TRACK_ID}',
    f'https://open.spotify.com/track/{TRACK_ID}/extra',
])
def test_parse_spotify_source_rejects_malformed_and_unsupported_values(value):
    with pytest.raises(ValueError):
        parse_spotify_source(value)


def _player_for_source_resolution():
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._sp = Mock()
    player._auth_manager = Mock()
    player._is_authenticated = Mock(return_value=True)
    return player


@pytest.mark.parametrize(('source_type', 'source_id', 'value', 'metadata',
                          'expected_name', 'expected_subtitle', 'expected_image'), [
    (
        'track',
        TRACK_ID,
        f'spotify:track:{TRACK_ID}',
        {
            'name': 'The Track',
            'artists': [{'name': 'First Artist'}, {'name': 'Second Artist'}],
            'album': {'images': [{'url': 'https://i.scdn.co/track-cover'}]},
        },
        'The Track',
        'First Artist, Second Artist',
        'https://i.scdn.co/track-cover',
    ),
    (
        'album',
        ALBUM_ID,
        f'https://open.spotify.com/album/{ALBUM_ID}?si=ignored',
        {
            'name': 'The Album',
            'artists': [{'name': 'Album Artist'}],
            'images': [{'url': 'https://i.scdn.co/album-cover'}],
        },
        'The Album',
        'Album Artist',
        'https://i.scdn.co/album-cover',
    ),
    (
        'playlist',
        PLAYLIST_ID,
        f'https://open.spotify.com/playlist/{PLAYLIST_ID}',
        {
            'name': 'The Playlist',
            'owner': {'display_name': 'Playlist Owner', 'id': 'owner-id'},
            'images': [{'url': 'https://i.scdn.co/playlist-cover'}],
        },
        'The Playlist',
        'Playlist Owner',
        'https://i.scdn.co/playlist-cover',
    ),
])
def test_resolve_source_normalizes_supported_spotify_metadata(
        source_type, source_id, value, metadata, expected_name,
        expected_subtitle, expected_image):
    player = _player_for_source_resolution()
    getattr(player._sp, source_type).return_value = metadata

    result = player.resolve_source(value)

    assert result == {
        'uri': f'spotify:{source_type}:{source_id}',
        'external_url': f'https://open.spotify.com/{source_type}/{source_id}',
        'type': source_type,
        'name': expected_name,
        'subtitle': expected_subtitle,
        'image_url': expected_image,
    }
    getattr(player._sp, source_type).assert_called_once_with(source_id)


@pytest.mark.parametrize(('source_type', 'source_id'), [
    ('track', TRACK_ID),
    ('album', ALBUM_ID),
    ('playlist', PLAYLIST_ID),
])
def test_resolve_source_uri_and_share_url_have_same_canonical_identity(
        source_type, source_id):
    player = _player_for_source_resolution()
    getattr(player._sp, source_type).return_value = {}

    uri_result = player.resolve_source(f'spotify:{source_type}:{source_id}')
    url_result = player.resolve_source(
        f'https://open.spotify.com/{source_type}/{source_id}?si=ignored')

    assert uri_result['uri'] == url_result['uri']
    assert uri_result['external_url'] == url_result['external_url']


@pytest.mark.parametrize('value', [
    'not Spotify',
    f'spotify:artist:{TRACK_ID}',
    f'https://open.spotify.com/show/{ALBUM_ID}',
])
def test_resolve_source_returns_invalid_source_without_calling_spotify(value):
    player = _player_for_source_resolution()

    assert player.resolve_source(value) == {'error': 'invalid_source'}
    player._sp.track.assert_not_called()
    player._sp.album.assert_not_called()
    player._sp.playlist.assert_not_called()


def test_resolve_source_returns_authentication_unavailable_without_client():
    player = PlayerSpotify.__new__(PlayerSpotify)
    player._sp = None
    player._auth_manager = None

    assert player.resolve_source(
        f'spotify:track:{TRACK_ID}'
    ) == {'error': 'authentication_unavailable'}


def test_resolve_source_returns_authentication_unavailable_without_token():
    player = _player_for_source_resolution()
    player._is_authenticated.return_value = False

    assert player.resolve_source(
        f'spotify:track:{TRACK_ID}'
    ) == {'error': 'authentication_unavailable'}
    player._sp.track.assert_not_called()


@pytest.mark.parametrize('status', [401, 403])
def test_resolve_source_maps_spotify_auth_rejection_to_authentication_unavailable(
        status):
    player = _player_for_source_resolution()
    player._sp.track.side_effect = _spotify_api_error(
        status, 'token rejected; access_token=do-not-leak')

    assert player.resolve_source(
        f'spotify:track:{TRACK_ID}'
    ) == {'error': 'authentication_unavailable'}


def test_resolve_source_maps_oauth_refresh_failure_to_authentication_unavailable():
    class SpotifyOauthError(RuntimeError):
        pass

    player = _player_for_source_resolution()
    player._sp.track.side_effect = SpotifyOauthError(
        'refresh failed; refresh_token=do-not-leak')

    with patch.object(player_module.logger, 'warning') as warning:
        result = player.resolve_source(f'spotify:track:{TRACK_ID}')

    assert result == {'error': 'authentication_unavailable'}
    assert 'do-not-leak' not in repr(result)
    assert 'do-not-leak' not in repr(warning.call_args)


@pytest.mark.parametrize(('source_type', 'source_id', 'metadata'), [
    ('track', TRACK_ID, {'album': {}}),
    ('album', ALBUM_ID, {}),
    ('playlist', PLAYLIST_ID, {'owner': {}}),
])
def test_resolve_source_tolerates_missing_metadata_and_artwork(
        source_type, source_id, metadata):
    player = _player_for_source_resolution()
    getattr(player._sp, source_type).return_value = metadata

    result = player.resolve_source(f'spotify:{source_type}:{source_id}')

    assert result['name'] == ''
    assert result['subtitle'] == ''
    assert result['image_url'] == ''


def test_resolve_source_uses_first_valid_image_and_playlist_owner_id_fallback():
    player = _player_for_source_resolution()
    player._sp.playlist.return_value = {
        'name': 'Playlist',
        'owner': {'display_name': '', 'id': 'owner-id'},
        'images': [None, {}, {'url': ''}, {'url': 'https://i.scdn.co/valid'}],
    }

    result = player.resolve_source(f'spotify:playlist:{PLAYLIST_ID}')

    assert result['subtitle'] == 'owner-id'
    assert result['image_url'] == 'https://i.scdn.co/valid'


def _spotify_api_error(status, message):
    error = RuntimeError(message)
    error.http_status = status
    return error


@pytest.mark.parametrize('failure', [
    None,
    _spotify_api_error(404, 'missing item'),
])
def test_resolve_source_returns_not_found_for_missing_spotify_content(failure):
    player = _player_for_source_resolution()
    if failure is None:
        player._sp.track.return_value = None
    else:
        player._sp.track.side_effect = failure

    assert player.resolve_source(
        f'spotify:track:{TRACK_ID}'
    ) == {'error': 'not_found'}


@pytest.mark.parametrize('failure', [
    _spotify_api_error(429, 'rate limited; access_token=do-not-leak'),
    _spotify_api_error(500, 'Spotify failed; client_secret=do-not-leak'),
    RuntimeError('timeout containing bearer do-not-leak'),
])
def test_resolve_source_returns_safe_error_for_transient_spotify_failure(failure):
    player = _player_for_source_resolution()
    player._sp.track.side_effect = failure

    with patch.object(player_module.logger, 'warning') as warning:
        result = player.resolve_source(f'spotify:track:{TRACK_ID}')

    assert result == {'error': 'spotify_unavailable'}
    assert 'do-not-leak' not in repr(result)
    assert 'do-not-leak' not in repr(warning.call_args)
