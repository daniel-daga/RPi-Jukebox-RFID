# -*- coding: utf-8 -*-
"""A stateful, in-memory emulation of the Spotify Web API (spotipy surface)

Instead of hand-crafting one canned ``Mock`` response per call, tests run
against a small simulation of a Spotify Connect account: a music catalog,
Connect devices, and one playback session whose progress advances on a
deterministic fake clock. The emulator also reproduces the real-world
Connect quirks the plugin must handle:

* a freshly seeded librespot device that is listed by ``devices()`` but
  rejects ``start_playback`` with *Device not found* until playback has
  been transferred to it once (``needs_activation``)
* transfers that are themselves rejected shortly after login
  (``rejected_transfers``)
* sessions reporting a large negative progress timeline while the value
  keeps advancing (``progress_offset_ms``)

This allows complete scenarios (card swipe -> playback -> status polling)
to run deterministically on any machine: no Raspberry Pi, no network, no
Spotify account.
"""

from copy import deepcopy


class FakeClock:
    """Deterministic time source; ``sleep`` advances it instead of waiting"""

    def __init__(self, start=1_700_000_000.0):
        self.current = start

    def now(self):
        return self.current

    def advance(self, seconds):
        self.current += seconds

    # Stand-in for time.sleep in code under test
    sleep = advance


class FakeSpotifyException(Exception):
    """Mimics spotipy.SpotifyException (http_status/msg/reason attributes)"""

    def __init__(self, http_status, msg, reason=''):
        super().__init__(f'http status: {http_status}, {msg}')
        self.http_status = http_status
        self.msg = msg
        self.reason = reason


class FakeSpotify:
    """Drop-in replacement for a ``spotipy.Spotify`` client

    Implements exactly the Web API surface the playerspotify plugin uses,
    backed by mutable account state that tests set up and inspect directly.
    """

    def __init__(self, clock=None):
        self.clock = clock or FakeClock()
        self.tracks = {}            # track id -> Web-API-shaped track object
        self.contexts = {}          # context uri -> catalog entry (album/playlist)
        self.connect_devices = []   # [{'id', 'name', 'type', 'volume_percent'}]
        self.needs_activation = set()   # device ids rejecting playback until transferred
        self.rejected_transfers = {}    # device id -> transfers to reject before accepting
        self.progress_offset_ms = 0     # <0 simulates the negative-progress Connect quirk
        self.user = {'id': 'test-user', 'display_name': 'Test User', 'email': ''}
        self.calls = []             # [(method name, kwargs)] in call order
        self._session = None        # current playback session, None = nothing playing

    # ------------------------------------------------------------------
    # Account state setup (test-facing)
    # ------------------------------------------------------------------

    def add_track(self, track_id, name='', artists=(), duration_s=180.0,
                  album_name='', image_url=''):
        """Register a track in the catalog. Returns its Spotify URI."""
        self.tracks[track_id] = {
            'id': track_id,
            'uri': f'spotify:track:{track_id}',
            'name': name or track_id,
            'artists': [{'name': artist} for artist in artists],
            'duration_ms': int(duration_s * 1000),
            'album': {
                'name': album_name,
                'images': [{'url': image_url}] if image_url else [],
            },
        }
        return self.tracks[track_id]['uri']

    def _add_context(self, context_type, context_id, name, track_ids, extra):
        uri = f'spotify:{context_type}:{context_id}'
        entry = {'type': context_type, 'id': context_id, 'uri': uri,
                 'name': name, 'track_ids': list(track_ids)}
        entry.update(extra)
        self.contexts[uri] = entry
        return uri

    def add_album(self, album_id, name, track_ids, artists=(), image_url=''):
        """Register an album over existing tracks. Returns its Spotify URI."""
        return self._add_context('album', album_id, name, track_ids, {
            'artists': [{'name': artist} for artist in artists],
            'images': [{'url': image_url}] if image_url else [],
        })

    def add_playlist(self, playlist_id, name, track_ids, owner='Playlist Owner',
                     image_url=''):
        """Register a playlist over existing tracks. Returns its Spotify URI."""
        return self._add_context('playlist', playlist_id, name, track_ids, {
            'owner': {'display_name': owner, 'id': owner.lower().replace(' ', '-')},
            'images': [{'url': image_url}] if image_url else [],
        })

    def add_device(self, device_id, name, device_type='Speaker', volume_percent=75,
                   needs_activation=False, reject_transfers=0):
        """Register a Spotify Connect device on the account"""
        self.connect_devices.append({
            'id': device_id, 'name': name, 'type': device_type,
            'volume_percent': volume_percent,
        })
        if needs_activation:
            self.needs_activation.add(device_id)
        if reject_transfers:
            self.rejected_transfers[device_id] = reject_transfers

    def remove_device(self, device_id):
        """Remove a Connect device (e.g. simulate a librespot restart)"""
        self.connect_devices = [d for d in self.connect_devices if d['id'] != device_id]
        self.needs_activation.discard(device_id)

    # ------------------------------------------------------------------
    # Test-facing state inspection
    # ------------------------------------------------------------------

    @property
    def is_playing(self):
        return bool(self._session and self._session['playing'])

    @property
    def current_track_id(self):
        """Id of the track the session is currently on (progress-synced)"""
        self._sync()
        if not self._session:
            return None
        return self._session['track_ids'][self._session['index']]

    @property
    def progress_ms(self):
        """True (un-offset) progress within the current track"""
        self._sync()
        return int(self._session['base_ms']) if self._session else None

    @property
    def playback_device_id(self):
        return self._session['device_id'] if self._session else None

    def call_names(self):
        return [name for name, _kwargs in self.calls]

    # ------------------------------------------------------------------
    # Session mechanics
    # ------------------------------------------------------------------

    def _current_duration(self):
        session = self._session
        track = self.tracks[session['track_ids'][session['index']]]
        return track['duration_ms']

    def _sync(self):
        """Advance session progress to 'now', moving through the queue

        When the queue is exhausted with repeat off, progress pins at the
        track end while ``is_playing`` stays True — exactly the Connect
        behaviour the plugin's stop detection handles.
        """
        session = self._session
        if not session or not session['playing']:
            return
        elapsed = session['base_ms'] + (self.clock.now() - session['anchor']) * 1000
        while True:
            duration = self._current_duration()
            if elapsed < duration or duration <= 0:
                break
            if session['repeat'] == 'track':
                elapsed -= duration
            elif session['index'] + 1 < len(session['track_ids']):
                session['index'] += 1
                elapsed -= duration
            elif session['repeat'] == 'context':
                session['index'] = 0
                elapsed -= duration
            else:
                elapsed = duration
                break
        session['base_ms'] = elapsed
        session['anchor'] = self.clock.now()

    def _new_session(self, device_id, track_ids, context_uri):
        previous = self._session
        self._session = {
            'device_id': device_id,
            'track_ids': list(track_ids),
            'index': 0,
            'context_uri': context_uri,
            'playing': True,
            'base_ms': 0.0,
            'anchor': self.clock.now(),
            'shuffle': previous['shuffle'] if previous else False,
            'repeat': previous['repeat'] if previous else 'off',
        }

    def _known_device_or_raise(self, device_id):
        if device_id is None:
            if self._session:
                return self._session['device_id']
            raise FakeSpotifyException(
                404, 'Player command failed: No active device found',
                reason='NO_ACTIVE_DEVICE')
        if device_id not in {device['id'] for device in self.connect_devices}:
            raise FakeSpotifyException(404, 'Device not found')
        return device_id

    def _record(self, method, **kwargs):
        self.calls.append((method, kwargs))

    # ------------------------------------------------------------------
    # spotipy Web API surface (plugin-facing)
    # ------------------------------------------------------------------

    def me(self):
        self._record('me')
        return dict(self.user)

    def devices(self):
        self._record('devices')
        active_id = self.playback_device_id
        return {'devices': [
            {'id': device['id'], 'name': device['name'], 'type': device['type'],
             'is_active': device['id'] == active_id,
             'volume_percent': device['volume_percent']}
            for device in self.connect_devices
        ]}

    def current_playback(self):
        self._record('current_playback')
        self._sync()
        session = self._session
        if not session:
            return None
        track = self.tracks[session['track_ids'][session['index']]]
        return {
            'device': {'id': session['device_id'],
                       'volume_percent': self._device_volume(session['device_id'])},
            'is_playing': session['playing'],
            'progress_ms': int(session['base_ms']) + self.progress_offset_ms,
            'shuffle_state': session['shuffle'],
            'repeat_state': session['repeat'],
            'context': ({'uri': session['context_uri']}
                        if session['context_uri'] else None),
            'item': deepcopy(track),
        }

    def _device_volume(self, device_id):
        for device in self.connect_devices:
            if device['id'] == device_id:
                return device['volume_percent']
        return 0

    def start_playback(self, device_id=None, context_uri=None, uris=None):
        self._record('start_playback', device_id=device_id,
                     context_uri=context_uri, uris=uris)
        device = self._known_device_or_raise(device_id)
        if device in self.needs_activation:
            raise FakeSpotifyException(404, 'Device not found')
        self._sync()
        if uris:
            track_ids = [uri.rsplit(':', 1)[-1] for uri in uris]
            for track_id in track_ids:
                if track_id not in self.tracks:
                    raise FakeSpotifyException(404, 'Non existing id', reason='')
            self._new_session(device, track_ids, None)
        elif context_uri:
            context = self.contexts.get(context_uri)
            if context is None:
                raise FakeSpotifyException(404, 'Non existing id', reason='')
            self._new_session(device, context['track_ids'], context_uri)
        else:
            # resume
            if self._session is None:
                raise FakeSpotifyException(
                    404, 'Player command failed: Nothing playing',
                    reason='NO_ACTIVE_DEVICE')
            self._session['playing'] = True
            self._session['anchor'] = self.clock.now()
            self._session['device_id'] = device

    def pause_playback(self, device_id=None):
        self._record('pause_playback', device_id=device_id)
        self._sync()
        if self._session:
            self._session['playing'] = False

    def transfer_playback(self, device_id, force_play=False):
        self._record('transfer_playback', device_id=device_id, force_play=force_play)
        if device_id not in {device['id'] for device in self.connect_devices}:
            raise FakeSpotifyException(404, 'Device not found')
        remaining = self.rejected_transfers.get(device_id, 0)
        if remaining > 0:
            self.rejected_transfers[device_id] = remaining - 1
            raise FakeSpotifyException(404, 'Device not found')
        self.needs_activation.discard(device_id)
        if self._session:
            self._sync()
            self._session['device_id'] = device_id
            if force_play:
                self._session['playing'] = True
                self._session['anchor'] = self.clock.now()

    def next_track(self, device_id=None):
        self._record('next_track', device_id=device_id)
        self._sync()
        session = self._session
        if not session:
            return
        if session['index'] + 1 < len(session['track_ids']):
            session['index'] += 1
        elif session['repeat'] == 'context':
            session['index'] = 0
        session['base_ms'] = 0.0
        session['anchor'] = self.clock.now()

    def previous_track(self, device_id=None):
        self._record('previous_track', device_id=device_id)
        self._sync()
        session = self._session
        if not session:
            return
        session['index'] = max(0, session['index'] - 1)
        session['base_ms'] = 0.0
        session['anchor'] = self.clock.now()

    def seek_track(self, position_ms, device_id=None):
        self._record('seek_track', position_ms=position_ms, device_id=device_id)
        self._sync()
        session = self._session
        if not session:
            return
        session['base_ms'] = float(min(max(0, position_ms), self._current_duration()))
        session['anchor'] = self.clock.now()

    def shuffle(self, state, device_id=None):
        self._record('shuffle', state=state, device_id=device_id)
        if self._session:
            self._session['shuffle'] = bool(state)

    def repeat(self, state, device_id=None):
        self._record('repeat', state=state, device_id=device_id)
        if self._session:
            self._session['repeat'] = state

    # Catalog lookups (used by resolve_source)

    def track(self, track_id):
        self._record('track', track_id=track_id)
        if track_id not in self.tracks:
            raise FakeSpotifyException(404, 'Non existing id', reason='')
        return deepcopy(self.tracks[track_id])

    def _context_lookup(self, context_type, context_id):
        entry = self.contexts.get(f'spotify:{context_type}:{context_id}')
        if entry is None or entry['type'] != context_type:
            raise FakeSpotifyException(404, 'Non existing id', reason='')
        result = {key: deepcopy(value) for key, value in entry.items()
                  if key not in ('track_ids', 'type')}
        return result

    def album(self, album_id):
        self._record('album', album_id=album_id)
        return self._context_lookup('album', album_id)

    def playlist(self, playlist_id):
        self._record('playlist', playlist_id=playlist_id)
        return self._context_lookup('playlist', playlist_id)


class FakeSpotifyOAuth:
    """Mimics spotipy.oauth2.SpotifyOAuth with an always-valid cached token"""

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None,
                 scope=None, cache_path=None, open_browser=False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.cache_path = cache_path
        self.cached_token = {'access_token': 'fake-access-token',
                             'scope': scope or ''}

    def get_cached_token(self):
        return self.cached_token

    def get_access_token(self, code=None, as_dict=True):
        self.cached_token = {'access_token': f'fake-access-token-{code}',
                             'scope': self.scope or ''}
        if as_dict:
            return dict(self.cached_token)
        return self.cached_token['access_token']

    def get_authorize_url(self):
        return (f'https://accounts.spotify.com/authorize'
                f'?client_id={self.client_id}&redirect_uri={self.redirect_uri}')
