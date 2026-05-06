# -*- coding: utf-8 -*-
"""
Package for interfacing with the Spotify Web API

Allows triggering Spotify playback (tracks, albums, playlists) via RFID cards.
Requires a Spotify Premium account and a registered Spotify Developer App.

Setup (one-time):
1. Create a Spotify App at https://developer.spotify.com/dashboard
2. In the app settings add this Redirect URI:
       http://<your-pi-hostname-or-ip>:8888/callback
3. Add your credentials to jukebox.yaml under 'playerspotify' and enable the module
4. Open the Jukebox web UI → Settings → Spotify → click "Connect with Spotify"
5. Authorise in your browser — the token is saved automatically

Card configuration example (cards.yaml):
    '<card-id>':
      package: spotify
      plugin: ctrl
      method: play_card
      args: ['spotify:playlist:37i9dQZF1DXcBWIGoYBM5M']
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import jukebox.cfghandler
import jukebox.plugs as plugs
from jukebox.NvManager import nv_manager

logger = logging.getLogger('jb.PlayerSpotify')
cfg = jukebox.cfghandler.get_handler('jukebox')

SECOND_SWIPE_ACTIONS = ['toggle', 'play', 'skip', 'rewind', 'none']


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler that catches the Spotify OAuth redirect"""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == '/callback' and 'code' in params:
            self.server.auth_code = params['code'][0]
            body = (b'<html><body style="font-family:sans-serif;text-align:center;padding:40px">'
                    b'<h2>Spotify connected!</h2>'
                    b'<p>You can close this tab and return to the Jukebox.</p>'
                    b'</body></html>')
            self.send_response(200)
        else:
            body = (b'<html><body style="font-family:sans-serif;text-align:center;padding:40px">'
                    b'<h2>Authorisation failed.</h2>'
                    b'<p>Please try again from the Jukebox settings.</p>'
                    b'</body></html>')
            self.send_response(400)

        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.debug(f"OAuth server: {format % args}")


class PlayerSpotify:
    """Spotify player plugin — controls Spotify playback via the Web API"""

    def __init__(self):
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        self._SpotifyOAuth = SpotifyOAuth

        self.nvm = nv_manager()
        status_file = cfg.setndefault('playerspotify', 'status_file',
                                      value='../../shared/settings/spotify_player_status.json')
        self.spotify_status = self.nvm.load(status_file)

        if not self.spotify_status:
            self.spotify_status['player_status'] = {'last_played_uri': ''}
            self.spotify_status['device_id'] = None
            self.spotify_status.save_to_json()

        # Reset on startup for correct second-swipe detection (mirrors MPD behaviour)
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

        # Device ID: prefer persisted value, then config, then None (= active device)
        self.device_id = (self.spotify_status.get('device_id')
                          or cfg.setndefault('playerspotify', 'device_id', value=None))

        self._scope = ('user-read-playback-state '
                       'user-modify-playback-state '
                       'user-read-currently-playing')

        self._lock = threading.RLock()
        self._oauth_server = None
        self._oauth_thread = None
        self._sp = None
        self._auth_manager = None

        import spotipy as _spotipy
        self._spotipy = _spotipy

        self._init_auth_manager()

    def _init_auth_manager(self):
        """Initialise (or reinitialise) the Spotify auth manager and client from current config."""
        client_id = cfg.getn('playerspotify', 'client_id', default='')
        client_secret = cfg.getn('playerspotify', 'client_secret', default='')
        self._redirect_uri = cfg.setndefault('playerspotify', 'redirect_uri',
                                             value='http://127.0.0.1:8888/callback')
        cache_path = cfg.setndefault('playerspotify', 'token_cache',
                                     value='../../shared/settings/.spotify_token')

        if not client_id or not client_secret:
            logger.warning("Spotify: client_id or client_secret not configured. "
                           "Set credentials via Settings → Spotify.")
            self._sp = None
            self._auth_manager = None
            return

        self._auth_manager = self._SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=self._redirect_uri,
            scope=self._scope,
            cache_path=cache_path,
            open_browser=False,
        )
        self._sp = self._spotipy.Spotify(auth_manager=self._auth_manager)

        if not self._is_authenticated():
            logger.info("Spotify: no cached token — start auth flow from the web UI "
                        "(Settings → Spotify → Connect with Spotify)")
            self._start_auth_server()
        else:
            logger.info("Spotify player initialised (authenticated)")

    # ------------------------------------------------------------------
    # Internal helpers
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

    def _is_configured(self):
        """Return True if credentials are set and the Spotify client is ready"""
        return self._sp is not None

    def _is_authenticated(self):
        """Return True if a valid (or refreshable) token is cached"""
        if self._auth_manager is None:
            return False
        try:
            token = self._auth_manager.get_cached_token()
            return token is not None
        except Exception:
            return False

    def _start_auth_server(self):
        """Start a temporary HTTP server to receive the OAuth callback"""
        if self._oauth_server is not None:
            return  # already running

        port = int(urlparse(self._redirect_uri).port or 8888)
        try:
            server = HTTPServer(('', port), _OAuthCallbackHandler)
            server.auth_code = None
            server.timeout = 1  # allow periodic shutdown checks
            self._oauth_server = server
        except OSError as e:
            logger.error(f"Spotify: cannot start OAuth callback server on port {port}: {e}")
            return

        def _serve():
            logger.info(f"Spotify OAuth callback server listening on port {port}")
            while self._oauth_server is not None and server.auth_code is None:
                server.handle_request()
            if server.auth_code:
                self._handle_auth_code(server.auth_code)
            self._oauth_server = None
            logger.info("Spotify OAuth callback server stopped")

        self._oauth_thread = threading.Thread(target=_serve, name='spotify-oauth', daemon=True)
        self._oauth_thread.start()

    def _stop_auth_server(self):
        self._oauth_server = None  # signals the serve loop to exit

    def _handle_auth_code(self, code):
        """Exchange the OAuth code for a token and reinitialise the client"""
        try:
            self._auth_manager.get_access_token(code, as_dict=False)
            logger.info("Spotify: OAuth token obtained — player is now active")
        except Exception as e:
            logger.error(f"Spotify: failed to exchange auth code: {e}")

    def exit(self):
        self._stop_auth_server()
        self.nvm.save_all()

    # ------------------------------------------------------------------
    # Auth / config RPC methods
    # ------------------------------------------------------------------

    @plugs.tag
    def get_config(self) -> dict:
        """Return current Spotify configuration. Client secret is never returned."""
        return {
            'client_id': cfg.getn('playerspotify', 'client_id', default=''),
            'has_client_secret': bool(cfg.getn('playerspotify', 'client_secret', default='')),
            'redirect_uri': cfg.getn('playerspotify', 'redirect_uri',
                                     default='http://127.0.0.1:8888/callback'),
        }

    @plugs.tag
    def set_config(self, client_id: str, client_secret: str, redirect_uri: str) -> dict:
        """
        Save Spotify credentials to jukebox.yaml and reinitialise the player.

        Pass an empty string for client_secret to keep the existing secret unchanged.
        """
        with cfg:
            cfg.setn('playerspotify', 'client_id', value=client_id.strip())
            if client_secret.strip():
                cfg.setn('playerspotify', 'client_secret', value=client_secret.strip())
            cfg.setn('playerspotify', 'redirect_uri', value=redirect_uri.strip())
        cfg.save()
        self._stop_auth_server()
        self._init_auth_manager()
        logger.info("Spotify: configuration updated")
        return {'success': True}

    @plugs.tag
    def get_auth_status(self) -> dict:
        """Return authentication status and basic account info"""
        if not self._is_configured():
            return {
                'authenticated': False,
                'auth_in_progress': False,
                'configured': False,
                'redirect_uri': cfg.getn('playerspotify', 'redirect_uri',
                                         default='http://127.0.0.1:8888/callback'),
            }
        authenticated = self._is_authenticated()
        result = {
            'authenticated': authenticated,
            'auth_in_progress': self._oauth_server is not None,
            'configured': True,
            'redirect_uri': self._redirect_uri,
        }
        if authenticated:
            try:
                user = self._sp.me()
                result['user'] = user.get('display_name') or user.get('id', '')
                result['email'] = user.get('email', '')
            except Exception:
                pass
        return result

    @plugs.tag
    def get_auth_url(self) -> str:
        """Return the Spotify authorisation URL to present to the user"""
        if not self._is_configured():
            return ''
        if not self._is_authenticated() and self._oauth_server is None:
            self._start_auth_server()
        return self._auth_manager.get_authorize_url()

    @plugs.tag
    def disconnect(self) -> None:
        """Remove the cached token (forces re-authentication)"""
        import os
        cache_path = cfg.setndefault('playerspotify', 'token_cache',
                                     value='../../shared/settings/.spotify_token')
        try:
            os.remove(cache_path)
            logger.info("Spotify: token removed")
        except FileNotFoundError:
            pass
        if self._is_configured():
            self._start_auth_server()

    @plugs.tag
    def set_device(self, device_id) -> None:
        """Persist the Spotify Connect device to use for playback (None = active device)"""
        self.device_id = device_id or None
        self.spotify_status['device_id'] = self.device_id
        self.nvm.save_all()
        logger.info(f"Spotify: device set to {self.device_id!r}")

    @plugs.tag
    def get_second_swipe_action(self) -> str:
        """Return the current second-swipe action name"""
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
    # Playback control
    # ------------------------------------------------------------------

    def _require_sp(self, method_name: str) -> bool:
        """Log a warning and return False if the Spotify client is not ready."""
        if self._sp is None:
            logger.warning(f"Spotify: {method_name}() called but player is not configured.")
            return False
        return True

    @plugs.tag
    def play(self):
        """Resume playback on the configured Spotify device"""
        if not self._require_sp('play'):
            return
        with self._lock:
            try:
                self._sp.start_playback(device_id=self.device_id)
            except Exception as e:
                logger.error(f"play(): {e}")

    @plugs.tag
    def stop(self):
        """Pause Spotify playback"""
        with self._lock:
            try:
                self._sp.pause_playback(device_id=self.device_id)
            except Exception as e:
                logger.error(f"stop(): {e}")

    @plugs.tag
    def pause(self, state: int = 1):
        """Pause (state=1) or resume (state=0) playback"""
        with self._lock:
            try:
                if state == 1:
                    self._sp.pause_playback(device_id=self.device_id)
                else:
                    self._sp.start_playback(device_id=self.device_id)
            except Exception as e:
                logger.error(f"pause(state={state}): {e}")

    @plugs.tag
    def toggle(self):
        """Toggle between play and pause"""
        with self._lock:
            try:
                current = self._sp.current_playback()
                if current and current.get('is_playing'):
                    self._sp.pause_playback(device_id=self.device_id)
                else:
                    self._sp.start_playback(device_id=self.device_id)
            except Exception as e:
                logger.error(f"toggle(): {e}")

    @plugs.tag
    def next(self):
        """Skip to the next track"""
        with self._lock:
            try:
                self._sp.next_track(device_id=self.device_id)
            except Exception as e:
                logger.error(f"next(): {e}")

    @plugs.tag
    def prev(self):
        """Skip to the previous track"""
        with self._lock:
            try:
                self._sp.previous_track(device_id=self.device_id)
            except Exception as e:
                logger.error(f"prev(): {e}")

    @plugs.tag
    def rewind(self):
        """Seek to the beginning of the current track"""
        with self._lock:
            try:
                self._sp.seek_track(0, device_id=self.device_id)
            except Exception as e:
                logger.error(f"rewind(): {e}")

    @plugs.tag
    def play_uri(self, uri: str) -> None:
        """
        Play a Spotify URI directly.

        :param uri: Spotify URI, e.g. 'spotify:playlist:37i9dQZF1DXcBWIGoYBM5M'
                    Supports track, album, and playlist URIs.
        """
        with self._lock:
            try:
                parts = uri.split(':')
                uri_type = parts[1] if len(parts) >= 2 else 'unknown'
                if uri_type == 'track':
                    self._sp.start_playback(device_id=self.device_id, uris=[uri])
                else:
                    self._sp.start_playback(device_id=self.device_id, context_uri=uri)
                logger.info(f"Playing Spotify URI: {uri}")
            except Exception as e:
                logger.error(f"play_uri('{uri}'): {e}")

    @plugs.tag
    def play_card(self, uri: str) -> None:
        """
        Main RFID card entry point for Spotify playback.

        On first swipe: starts playing the Spotify URI.
        On second swipe of the same card: performs the configured
        second_swipe_action (default: toggle play/pause).

        :param uri: Spotify URI (track, album, or playlist)
        """
        last = self.spotify_status['player_status']['last_played_uri']
        logger.debug(f"play_card: uri={uri}, last_played={last}")
        is_second_swipe = last == uri

        if self.second_swipe_action is not None and is_second_swipe:
            logger.debug("Spotify: second swipe action")
            self.second_swipe_action()
        else:
            logger.debug("Spotify: first swipe — starting playback")
            self.spotify_status['player_status']['last_played_uri'] = uri
            self.play_uri(uri)

    # ------------------------------------------------------------------
    # Status / info
    # ------------------------------------------------------------------

    @plugs.tag
    def playerstatus(self) -> dict:
        """Return current Spotify playback status"""
        with self._lock:
            try:
                current = self._sp.current_playback()
                if not current:
                    return {'state': 'stop'}
                item = current.get('item') or {}
                return {
                    'state': 'play' if current.get('is_playing') else 'pause',
                    'uri': item.get('uri', ''),
                    'title': item.get('name', ''),
                    'artist': ', '.join(a['name'] for a in item.get('artists', [])),
                    'album': (item.get('album') or {}).get('name', ''),
                    'duration_ms': item.get('duration_ms', 0),
                    'progress_ms': current.get('progress_ms', 0),
                    'volume': (current.get('device') or {}).get('volume_percent', 0),
                }
            except Exception as e:
                logger.error(f"playerstatus(): {e}")
                return {}

    @plugs.tag
    def list_devices(self) -> list:
        """List available Spotify Connect devices and their IDs"""
        with self._lock:
            try:
                result = self._sp.devices()
                return result.get('devices', [])
            except Exception as e:
                logger.error(f"list_devices(): {e}")
                return []


player_ctrl: PlayerSpotify = None


@plugs.initialize
def initialize():
    global player_ctrl
    try:
        player_ctrl = PlayerSpotify()
        plugs.register(player_ctrl, name='ctrl')
        logger.info("Spotify player plugin loaded as 'spotify.ctrl'")
    except Exception as e:
        logger.error(f"Failed to initialise Spotify player: {e}")
        logger.error("Check that 'playerspotify' credentials are configured in jukebox.yaml.")
        raise


@plugs.atexit
def atexit(**ignored_kwargs):
    global player_ctrl
    if player_ctrl is not None:
        player_ctrl.exit()
