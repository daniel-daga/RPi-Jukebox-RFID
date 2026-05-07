# -*- coding: utf-8 -*-
"""
Package for controlling Spotify playback via the go-librespot local API.

go-librespot runs as a systemd user service on the Pi and handles
authentication + audio streaming. This plugin drives it via its HTTP API.

Requires go-librespot to be installed, running, and authenticated:
  systemctl --user status go-librespot

Card configuration example (cards.yaml):
    '<card-id>':
      package: spotify
      plugin: ctrl
      method: play_card
      args: ['spotify:playlist:37i9dQZF1DXcBWIGoYBM5M']
"""

import logging
import threading
import time

import requests

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.publishing as publishing
from jukebox.NvManager import nv_manager

logger = logging.getLogger('jb.PlayerSpotify')
cfg = jukebox.cfghandler.get_handler('jukebox')

SECOND_SWIPE_ACTIONS = ['toggle', 'play', 'skip', 'rewind', 'none']
_API = 'http://127.0.0.1:3678'


class PlayerSpotify:
    """Spotify player plugin — controls go-librespot via its local HTTP API."""

    def __init__(self):
        self.nvm = nv_manager()
        status_file = cfg.setndefault('playerspotify', 'status_file',
                                      value='../../shared/settings/spotify_player_status.json')
        self.spotify_status = self.nvm.load(status_file)

        if not self.spotify_status:
            self.spotify_status['player_status'] = {'last_played_uri': ''}
            self.spotify_status.save_to_json()

        # Reset on startup so the first card swipe always triggers playback
        self.spotify_status['player_status']['last_played_uri'] = ''

        self.second_swipe_action_dict = {
            'toggle': self.toggle,
            'play': self.play,
            'skip': self.next,
            'rewind': self.rewind,
            'none': lambda: None,
        }
        self.second_swipe_action = None
        self.second_swipe_action_name = 'toggle'
        self._decode_2nd_swipe_option()

        self._lock = threading.RLock()
        self._running = True
        # Elapsed-time tracking (go-librespot has no position field in /status)
        self._last_songid = ''
        self._play_start_time = None
        self._elapsed_at_pause = 0.0
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name='spotify-poll', daemon=True)
        self._poll_thread.start()

        logger.info("Spotify player plugin initialised (go-librespot API)")

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _decode_2nd_swipe_option(self):
        action = cfg.setndefault('playerspotify', 'second_swipe_action', 'alias',
                                 value='toggle').lower()
        if action in self.second_swipe_action_dict:
            self.second_swipe_action = self.second_swipe_action_dict[action]
            self.second_swipe_action_name = action
        else:
            logger.error(f"Invalid second_swipe_action '{action}'. Defaulting to 'toggle'.")
            self.second_swipe_action = self.toggle
            self.second_swipe_action_name = 'toggle'

    # ------------------------------------------------------------------
    # go-librespot API helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> dict:
        try:
            resp = requests.get(f'{_API}{path}', timeout=5)
            if resp.status_code == 204:
                return {}
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.RequestException as e:
            logger.error(f"go-librespot GET {path}: {e}")
            return {}

    def _post(self, path: str, **body) -> dict:
        try:
            resp = requests.post(
                f'{_API}{path}', json=body if body else None, timeout=5)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.RequestException as e:
            logger.error(f"go-librespot POST {path}: {e}")
            return {}

    # ------------------------------------------------------------------
    # Status polling → pub/sub
    # ------------------------------------------------------------------

    @staticmethod
    def _to_playerstatus(status: dict) -> dict:
        """Map go-librespot /status to the webapp-compatible playerstatus dict."""
        if not status:
            return {}

        stopped = status.get('stopped', True)
        paused = status.get('paused', False)
        state = 'stop' if stopped else ('pause' if paused else 'play')

        track = status.get('track') or {}
        artist_names = track.get('artist_names') or []
        uri = track.get('uri') or ''
        name = track.get('name') or ''

        return {
            'player': 'spotify',
            'state': state,
            'title': name,
            'artist': ', '.join(artist_names),
            'album': track.get('album_name') or '',
            'albumart': track.get('album_cover_url') or '',
            'uri': uri,
            'duration': (track.get('duration') or 0) // 1000,
            'volume': status.get('volume') or 0,
            # webapp compat: songid gates display; use name as fallback if uri absent
            'songid': uri or name,
            'random': '1' if status.get('shuffle_context') else '0',
            'repeat': '1' if status.get('repeat_context') else '0',
            'single': '1' if status.get('repeat_track') else '0',
        }

    def _poll_loop(self):
        """Poll /status every 2 s and publish playerstatus, tracking elapsed time locally."""
        while self._running:
            status = self._get('/status')
            ps = self._to_playerstatus(status)
            if ps:
                playing = not status.get('stopped', True) and not status.get('paused', False)
                current_songid = ps.get('songid', '')

                if current_songid != self._last_songid:
                    # New track: reset elapsed counter
                    self._last_songid = current_songid
                    self._elapsed_at_pause = 0.0
                    self._play_start_time = time.time() if playing else None
                elif playing:
                    if self._play_start_time is None:
                        # Resumed from pause
                        self._play_start_time = time.time()
                else:
                    # Paused or stopped: freeze elapsed
                    if self._play_start_time is not None:
                        self._elapsed_at_pause += time.time() - self._play_start_time
                        self._play_start_time = None

                if playing and self._play_start_time is not None:
                    elapsed = self._elapsed_at_pause + (time.time() - self._play_start_time)
                else:
                    elapsed = self._elapsed_at_pause

                ps['elapsed'] = round(elapsed, 1)
                publishing.get_publisher().send('playerstatus', ps)
            time.sleep(2)

    def exit(self):
        self._running = False
        self.nvm.save_all()

    # ------------------------------------------------------------------
    # Status / info RPC
    # ------------------------------------------------------------------

    @plugs.tag
    def get_auth_status(self) -> dict:
        """Return go-librespot authentication and connection status."""
        status = self._get('/status')
        if not status:
            return {'authenticated': False, 'error': 'go-librespot not reachable on port 3678'}
        username = status.get('username', '')
        return {
            'authenticated': bool(username),
            'username': username,
            'device_name': status.get('device_name', ''),
        }

    @plugs.tag
    def playerstatus(self) -> dict:
        """Return current Spotify playback status."""
        return self._to_playerstatus(self._get('/status'))

    @plugs.tag
    def get_second_swipe_action(self) -> str:
        """Return the current second-swipe action name."""
        return self.second_swipe_action_name

    @plugs.tag
    def set_second_swipe_action(self, action: str) -> None:
        """Set the second-swipe action. Must be one of: toggle, play, skip, rewind, none"""
        action = action.lower()
        if action not in self.second_swipe_action_dict:
            logger.error(f"Invalid second_swipe_action '{action}'")
            return
        self.second_swipe_action = self.second_swipe_action_dict[action]
        self.second_swipe_action_name = action

    # ------------------------------------------------------------------
    # Playback control RPC
    # ------------------------------------------------------------------

    @plugs.tag
    def play(self):
        """Resume playback."""
        with self._lock:
            self._post('/player/resume')

    @plugs.tag
    def stop(self):
        """Pause playback."""
        with self._lock:
            self._post('/player/pause')

    @plugs.tag
    def pause(self, state: int = 1):
        """Pause (state=1) or resume (state=0) playback."""
        with self._lock:
            self._post('/player/pause' if state == 1 else '/player/resume')

    @plugs.tag
    def toggle(self):
        """Toggle between play and pause."""
        with self._lock:
            status = self._get('/status')
            playing = status and not status.get('stopped') and not status.get('paused')
            self._post('/player/pause' if playing else '/player/resume')

    @plugs.tag
    def next(self):
        """Skip to the next track."""
        with self._lock:
            self._post('/player/next')

    @plugs.tag
    def prev(self):
        """Skip to the previous track."""
        with self._lock:
            self._post('/player/prev')

    @plugs.tag
    def rewind(self):
        """Seek to the beginning of the current track."""
        with self._lock:
            self._post('/player/seek', position=0)

    @plugs.tag
    def play_uri(self, uri: str) -> None:
        """Play a Spotify URI (track, album, or playlist)."""
        with self._lock:
            result = self._post('/player/play', uri=uri)
            logger.info(f"Playing Spotify URI: {uri} → {result}")

    @plugs.tag
    def play_card(self, uri: str) -> None:
        """
        Main RFID card entry point for Spotify playback.

        First swipe: starts playing the URI.
        Second swipe of the same card: performs the configured second_swipe_action.
        """
        last = self.spotify_status['player_status']['last_played_uri']
        if self.second_swipe_action is not None and last == uri:
            logger.debug("Spotify: second swipe → action")
            self.second_swipe_action()
        else:
            logger.debug(f"Spotify: first swipe → playing {uri}")
            self.spotify_status['player_status']['last_played_uri'] = uri
            self.play_uri(uri)


player_ctrl: PlayerSpotify = None


@plugs.initialize
def initialize():
    global player_ctrl
    try:
        player_ctrl = PlayerSpotify()
        plugs.register(player_ctrl, name='ctrl')
    except Exception as e:
        logger.error(f"Failed to initialise Spotify player: {e}")
        raise


@plugs.atexit
def atexit(**ignored_kwargs):
    global player_ctrl
    if player_ctrl is not None:
        player_ctrl.exit()
