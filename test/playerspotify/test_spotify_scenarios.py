# -*- coding: utf-8 -*-
"""End-to-end Spotify scenarios against the fake Web API emulator

Each test drives the real PlayerSpotify plugin (full constructor, real
player arbiter, real device resolution) through a complete user-visible
scenario — card swipes, transport commands, status polling — with only
the Spotify Web API, clock and ZMQ boundary faked. See conftest.py.
"""

import pytest


class DummyBackend:
    """Stand-in MPD backend for arbiter interplay tests"""

    def __init__(self):
        self.deactivations = 0

    def on_deactivate(self):
        self.deactivations += 1


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


def test_constructor_wires_plugin_into_the_jukebox(spotify_env):
    env = spotify_env

    # Registered as a backend with the (real) player arbiter
    assert 'spotify' in env.arbiter._backends
    assert env.arbiter._backends['spotify'] is env.player

    # Status poll timer created and started with the Web-API-friendly interval
    assert env.status_timer.started
    assert env.status_timer.interval == pytest.approx(2.0)

    # Authenticated via the cached token: no OAuth callback server running
    assert env.player._oauth_server is None

    # Persistent status file created next to the (temp) shared settings
    assert env.player.spotify_status['player_status']['last_played_uri'] == ''


# ---------------------------------------------------------------------------
# Card swipes
# ---------------------------------------------------------------------------


def test_first_swipe_plays_playlist_on_the_phoniebox_device(spotify_env):
    env = spotify_env

    env.player.play_card(env.playlist_uri)

    assert env.spotify.is_playing
    assert env.spotify.current_track_id == env.track_ids[0]
    assert env.spotify.playback_device_id == env.device_id
    assert env.arbiter.active_name == 'spotify'

    status = env.last_status()
    assert status['player'] == 'spotify'
    assert status['state'] == 'play'
    assert status['title'] == 'First Song'
    assert status['artist'] == 'Alpha Artist'
    assert status['albumart'] == 'https://i.scdn.co/image/first'
    assert float(status['elapsed']) == pytest.approx(0.0)
    assert float(status['duration']) == pytest.approx(180.0)

    rpc_status = env.player.playerstatus()
    assert rpc_status['state'] == 'play'
    assert rpc_status['title'] == 'First Song'


def test_second_swipe_toggles_pause_and_resume_without_losing_position(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)
    env.clock.advance(10)

    env.player.play_card(env.playlist_uri)   # second swipe -> pause

    assert not env.spotify.is_playing
    assert env.spotify.progress_ms == pytest.approx(10000, abs=1)
    assert env.last_status()['state'] == 'pause'

    env.clock.advance(60)                     # paused: no progress
    env.player.play_card(env.playlist_uri)   # third swipe -> resume

    assert env.spotify.is_playing
    assert env.spotify.progress_ms == pytest.approx(10000, abs=1)
    assert env.last_status()['state'] == 'play'
    assert float(env.last_status()['elapsed']) == pytest.approx(10.0, abs=0.001)


def test_swiping_a_different_card_switches_playback(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    env.player.play_card(env.track3_uri)

    assert env.spotify.is_playing
    assert env.spotify.current_track_id == env.track_ids[2]
    assert env.last_status()['title'] == 'Third Song'


def test_same_card_restarts_instead_of_toggling_after_mpd_interlude(spotify_env):
    env = spotify_env
    mpd = DummyBackend()
    env.arbiter.register_backend('mpd', mpd)
    env.player.play_card(env.playlist_uri)
    env.clock.advance(30)

    env.arbiter.claim_active('mpd')           # e.g. an MPD folder card

    # Losing the active slot silences Spotify
    assert not env.spotify.is_playing

    env.player.play_card(env.playlist_uri)   # same card again

    # Not a toggle: the playlist starts over and Spotify is active again
    assert env.spotify.is_playing
    assert env.spotify.current_track_id == env.track_ids[0]
    assert env.spotify.progress_ms == pytest.approx(0, abs=1)
    assert env.arbiter.active_name == 'spotify'
    # MPD was silenced on each of the two Spotify claims
    assert mpd.deactivations == 2


def test_configured_second_swipe_action_skip_advances_the_playlist(make_spotify_env):
    env = make_spotify_env(config_overrides={'second_swipe_action': {'alias': 'skip'}})
    env.player.play_card(env.playlist_uri)

    env.player.play_card(env.playlist_uri)

    assert env.spotify.is_playing
    assert env.spotify.current_track_id == env.track_ids[1]
    assert env.last_status()['title'] == 'Second Song'


# ---------------------------------------------------------------------------
# Status polling and publishing ownership
# ---------------------------------------------------------------------------


def test_status_poll_publishes_progress_only_while_spotify_is_active(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)
    env.clear_published()

    env.poll()
    assert float(env.last_status()['elapsed']) == pytest.approx(0.0)

    env.clock.advance(5)
    env.poll()
    assert float(env.last_status()['elapsed']) == pytest.approx(5.0, abs=0.001)

    env.arbiter.register_backend('mpd', DummyBackend())
    env.arbiter.claim_active('mpd')
    env.clear_published()

    env.poll()                                # inactive: publishes nothing

    assert env.statuses() == []


def test_playlist_advances_to_the_next_track_during_playback(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    env.clock.advance(185)                    # past First Song (180 s)
    env.poll()

    status = env.last_status()
    assert status['state'] == 'play'
    assert status['title'] == 'Second Song'
    assert float(status['elapsed']) == pytest.approx(5.0, abs=0.001)


def test_single_track_reports_stop_when_it_plays_to_the_end(spotify_env):
    env = spotify_env
    env.player.play_card(env.track1_uri)

    env.clock.advance(200)                    # past the 180 s duration
    env.poll()

    status = env.last_status()
    assert status['state'] == 'stop'
    assert float(status['elapsed']) == pytest.approx(180.0)

    env.clock.advance(10)                     # stays stopped on further polls
    env.poll()
    assert env.last_status()['state'] == 'stop'


def test_negative_progress_quirk_still_produces_an_advancing_seek_bar(spotify_env):
    env = spotify_env
    env.spotify.progress_offset_ms = -3_600_000

    env.player.play_card(env.track1_uri)
    env.clear_published()
    env.poll()
    assert float(env.last_status()['elapsed']) == pytest.approx(0.0)

    env.clock.advance(5)
    env.poll()
    assert float(env.last_status()['elapsed']) == pytest.approx(5.0, abs=0.001)


# ---------------------------------------------------------------------------
# Spotify Connect device handling
# ---------------------------------------------------------------------------


def test_fresh_librespot_device_is_activated_via_transfer_then_played(spotify_env):
    env = spotify_env
    env.spotify.needs_activation.add(env.device_id)
    started_at = env.clock.now()

    env.player.play_card(env.playlist_uri)

    assert env.spotify.is_playing
    assert env.spotify.playback_device_id == env.device_id
    assert env.spotify.call_names().count('transfer_playback') == 1
    # The settle wait ran against the fake clock, not real time
    assert env.clock.now() - started_at == pytest.approx(2.0)


def test_transfer_rejection_is_retried_until_the_device_accepts(spotify_env):
    env = spotify_env
    env.spotify.needs_activation.add(env.device_id)
    env.spotify.rejected_transfers[env.device_id] = 1
    started_at = env.clock.now()

    env.player.play_card(env.playlist_uri)

    assert env.spotify.is_playing
    assert env.spotify.call_names().count('transfer_playback') == 2
    assert env.clock.now() - started_at == pytest.approx(4.0)


def test_stale_device_id_after_librespot_restart_is_refreshed(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)   # resolves and caches the device id

    # librespot restart: same name, new Connect device id
    env.spotify.remove_device(env.device_id)
    env.spotify.add_device('phoniebox-after-restart', 'Phoniebox')

    env.player.play_card(env.track2_uri)

    assert env.spotify.is_playing
    assert env.spotify.playback_device_id == 'phoniebox-after-restart'
    assert 'transfer_playback' not in env.spotify.call_names()


# ---------------------------------------------------------------------------
# Unified playback engine (webapp / player.ctrl routing)
# ---------------------------------------------------------------------------


def test_webapp_transport_commands_route_to_spotify_via_the_arbiter(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    handled, _result = env.arbiter.route_from_default('toggle')
    assert handled is True
    assert not env.spotify.is_playing
    assert env.last_status()['state'] == 'pause'

    handled, _result = env.arbiter.route_from_default('seek', 42)
    assert handled is True
    assert env.spotify.progress_ms == 42000

    handled, _result = env.arbiter.route_from_default('next')
    assert handled is True
    assert env.spotify.current_track_id == env.track_ids[1]


def test_becoming_inactive_pauses_spotify_playback(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)
    env.arbiter.register_backend('mpd', DummyBackend())

    env.arbiter.claim_active('mpd')

    assert not env.spotify.is_playing


# ---------------------------------------------------------------------------
# Transport details
# ---------------------------------------------------------------------------


def test_next_and_prev_move_through_the_playlist(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    env.player.next()
    assert env.spotify.current_track_id == env.track_ids[1]
    assert env.last_status()['title'] == 'Second Song'

    env.player.next()
    assert env.spotify.current_track_id == env.track_ids[2]

    env.player.prev()
    assert env.spotify.current_track_id == env.track_ids[1]
    assert env.last_status()['title'] == 'Second Song'


def test_seek_converts_seconds_and_publishes_the_new_position(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    env.player.seek(30)

    assert env.spotify.progress_ms == 30000
    assert float(env.last_status()['elapsed']) == pytest.approx(30.0)


def test_shuffle_and_repeat_round_trip_through_the_web_api(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)

    env.player.shuffle('enable')
    assert env.last_status()['random'] == '1'

    env.player.shuffle('disable')
    assert env.last_status()['random'] == '0'

    env.player.repeat('toggle')               # off -> context
    status = env.last_status()
    assert (status['repeat'], status['single']) == ('1', '0')

    env.player.repeat('toggle')               # context -> track
    status = env.last_status()
    assert (status['repeat'], status['single']) == ('1', '1')

    env.player.repeat('toggle')               # track -> off
    status = env.last_status()
    assert (status['repeat'], status['single']) == ('0', '0')


def test_repeat_track_loops_the_same_song(spotify_env):
    env = spotify_env
    env.player.play_card(env.track1_uri)
    env.player.repeat('enable_repeat_single')

    env.clock.advance(190)                    # past the 180 s duration
    env.poll()

    status = env.last_status()
    assert status['state'] == 'play'
    assert status['title'] == 'First Song'
    assert float(status['elapsed']) == pytest.approx(10.0, abs=0.001)


# ---------------------------------------------------------------------------
# Card metadata resolution (web UI card wizard)
# ---------------------------------------------------------------------------


def test_resolve_source_reads_metadata_from_the_account_catalog(spotify_env):
    env = spotify_env
    playlist_id = env.playlist_uri.rsplit(':', 1)[-1]

    result = env.player.resolve_source(
        f'https://open.spotify.com/playlist/{playlist_id}?si=share-token')

    assert result == {
        'uri': env.playlist_uri,
        'external_url': f'https://open.spotify.com/playlist/{playlist_id}',
        'type': 'playlist',
        'name': 'Bedtime Songs',
        'subtitle': 'Playlist Owner',
        'image_url': '',
    }


def test_resolve_source_maps_unknown_content_to_not_found(spotify_env):
    env = spotify_env

    result = env.player.resolve_source('spotify:track:' + 'Y' * 22)

    assert result == {'error': 'not_found'}
