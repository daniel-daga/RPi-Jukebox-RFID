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

import components.player
import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.multitimer as multitimer
import jukebox.publishing as publishing
from jukebox.NvManager import nv_manager
from . import librespot_seeder
from .device_resolver import resolve_device_id

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
        # Device name: when no explicit device_id is selected, the playback
        # device is looked up by this name. Defaults to the librespot instance
        # running on the Pi itself (see setup_librespot.inc.sh)
        self.device_name = cfg.setndefault('playerspotify', 'device_name', value='Phoniebox')
        self._resolved_device_id = None

        # 'streaming' allows handing the token to librespot for auto-login
        self._scope = ('user-read-playback-state '
                       'user-modify-playback-state '
                       'user-read-currently-playing '
                       'streaming')

        # Automatic librespot login: logs the librespot instance on the Pi
        # into the Spotify account with the jukebox's own OAuth token, so the
        # device does not need to be activated from a phone/desktop app once
        self._librespot_auto_login = cfg.setndefault('playerspotify', 'librespot', 'auto_login', value=True)
        self._librespot_cache = cfg.setndefault('playerspotify', 'librespot', 'cache_dir',
                                                value='~/.cache/librespot')
        self._librespot_service = cfg.setndefault('playerspotify', 'librespot', 'service',
                                                  value='librespot.service')

        self._lock = threading.RLock()
        self._oauth_server = None
        self._oauth_thread = None
        self._sp = None
        self._auth_manager = None

        import spotipy as _spotipy
        self._spotipy = _spotipy

        self._init_auth_manager()

        # Take part in the unified playback engine: while Spotify is the
        # active backend it receives the player.ctrl.* transport commands
        # and owns the 'playerstatus' publishing topic
        components.player.arbiter.register_backend('spotify', self)

        # Status poll: publishes 'playerstatus' while Spotify is the active
        # player. The interval is Web-API friendly (rate limits!) - snappy UI
        # updates come from the immediate publish after each transport command.
        self.status_poll_interval = 2.0
        self.status_thread = multitimer.GenericEndlessTimerClass(
            'spotify.timer_status', self.status_poll_interval, self._status_poll)
        self.status_thread.start()

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
            self._seed_librespot_async()

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
            self._seed_librespot_async()
        except Exception as e:
            logger.error(f"Spotify: failed to exchange auth code: {e}")

    def _seed_librespot_async(self):
        """Log the local librespot into the Spotify account (background thread)

        Removes the need to activate the device once from a phone/desktop
        Spotify app: librespot gets the jukebox's own OAuth token and stores
        reusable credentials, so it reconnects by itself from then on.
        """
        if not self._librespot_auto_login or self._auth_manager is None:
            return
        threading.Thread(target=self._seed_librespot, name='spotify-librespot-seed',
                         daemon=True).start()

    def _seed_librespot(self):
        try:
            binary = librespot_seeder.find_librespot()
            if binary is None:
                logger.debug("librespot auto-login: librespot not installed - skipping "
                             "(run setup_librespot.inc.sh for playback on the Pi)")
                return
            if librespot_seeder.has_cached_credentials(self._librespot_cache):
                logger.debug("librespot auto-login: credentials already cached - nothing to do")
                return
            if not librespot_seeder.supports_access_token(binary):
                logger.warning("librespot auto-login: the installed librespot is too old for "
                               "--access-token (needs v0.5+). Update it, or activate the device "
                               "once by selecting it in a Spotify app on the same network.")
                return
            token_info = self._auth_manager.get_cached_token()
            if not token_info:
                return
            if 'streaming' not in (token_info.get('scope') or ''):
                logger.warning("librespot auto-login: the Spotify token lacks the 'streaming' "
                               "permission. Disconnect and re-connect Spotify in the web UI "
                               "(Settings → Spotify) to grant it.")
                return
            logger.info(f"librespot auto-login: logging device '{self.device_name}' "
                        "into the Spotify account...")
            if librespot_seeder.seed(binary, token_info['access_token'],
                                     self._librespot_cache, self.device_name):
                self._restart_librespot_service()
                # Force a fresh device lookup - the device appears on the account now
                self._resolved_device_id = None
                logger.info("librespot auto-login: success - the jukebox is now a "
                            "Spotify Connect device")
            else:
                logger.warning("librespot auto-login failed. Fallback: select the device "
                               f"'{self.device_name}' once in a Spotify app on the same network.")
        except Exception as e:
            logger.warning(f"librespot auto-login failed: {e.__class__.__name__}: {e}")

    def _restart_librespot_service(self):
        """Restart the librespot user service so it picks up the new credentials"""
        import subprocess
        try:
            subprocess.run(['systemctl', '--user', 'restart', self._librespot_service],
                           check=False, timeout=30, capture_output=True)
        except Exception as e:
            logger.debug(f"Could not restart {self._librespot_service}: {e}")

    def exit(self):
        self._stop_auth_server()
        self.status_thread.cancel()
        self.nvm.save_all()

    # ------------------------------------------------------------------
    # Unified playback engine integration
    # ------------------------------------------------------------------

    def _claim_active(self):
        """Make Spotify the active player backend (silences MPD)"""
        components.player.arbiter.claim_active('spotify')

    def on_deactivate(self):
        """Called by the player arbiter when another backend becomes the active player"""
        if self._sp is None:
            return
        with self._lock:
            try:
                current = self._sp.current_playback()
                if current and current.get('is_playing'):
                    logger.debug("Pausing Spotify playback - another player backend became active")
                    self._sp.pause_playback(device_id=self.device_id)
            except Exception as e:
                logger.debug(f"on_deactivate(): {e}")

    def _build_status(self):
        """Build a 'playerstatus' payload with MPD-compatible keys for the webapp

        :return: status dict, or None on a transient Web API error
        """
        status = {'player': 'spotify', 'state': 'stop'}
        if self._sp is None:
            return status
        try:
            with self._lock:
                current = self._sp.current_playback()
        except Exception as e:
            logger.debug(f"_build_status(): {e}")
            return None
        if not current:
            return status
        item = current.get('item') or {}
        repeat_state = current.get('repeat_state', 'off')
        status.update({
            'state': 'play' if current.get('is_playing') else 'pause',
            # songid enables the transport buttons in the webapp
            'songid': item.get('id') or item.get('uri', ''),
            'file': item.get('uri', ''),
            'title': item.get('name', ''),
            'artist': ', '.join(a['name'] for a in item.get('artists', [])),
            'album': (item.get('album') or {}).get('name', ''),
            'elapsed': str((current.get('progress_ms') or 0) / 1000),
            'duration': str((item.get('duration_ms') or 0) / 1000),
            'random': '1' if current.get('shuffle_state') else '0',
            'repeat': '1' if repeat_state != 'off' else '0',
            'single': '1' if repeat_state == 'track' else '0',
        })
        return status

    def _status_poll(self):
        if not components.player.arbiter.is_active('spotify'):
            return
        status = self._build_status()
        if status is not None:
            publishing.get_publisher().send('playerstatus', status)

    def _publish_status(self, state_hint: str = None):
        """Publish the player status right away (called after transport commands)

        :param state_hint: the state the command just produced; the Web API
            often still reports the old state for a moment, so the known
            outcome overrides it until the next poll
        """
        if not components.player.arbiter.is_active('spotify'):
            return
        status = self._build_status()
        if status is None:
            return
        if state_hint is not None and status['state'] != 'stop':
            status['state'] = state_hint
        publishing.get_publisher().send('playerstatus', status)

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
        """Persist the Spotify Connect device to use for playback

        None = no explicit device: the device is then resolved by the
        configured device_name (falling back to the account's active device)
        """
        self.device_id = device_id or None
        self._resolved_device_id = None
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

    def _playback_device(self, refresh: bool = False):
        """Return the device id to start playback on

        An explicitly selected device_id (web UI / config) always wins.
        Otherwise the device is looked up by the configured device_name —
        typically the librespot instance on the Pi itself — so playback works
        without any device being 'active' on the account. Returns None when
        nothing matches (the Web API then targets the active device).
        """
        if self.device_id:
            return self.device_id
        if not self.device_name:
            return None
        if refresh or self._resolved_device_id is None:
            try:
                devices = self._sp.devices().get('devices', [])
            except Exception as e:
                logger.debug(f"_playback_device(): device list failed: {e}")
                return self._resolved_device_id
            self._resolved_device_id = resolve_device_id(devices, self.device_name)
            if self._resolved_device_id is None:
                logger.warning(f"Spotify: no Connect device named '{self.device_name}' found. "
                               f"Available: {[d.get('name') for d in devices]}. "
                               "Is librespot running on the Pi?")
        return self._resolved_device_id

    def _start_playback(self, **kwargs):
        """start_playback with device resolution and one retry

        A cached device id can go stale when librespot restarts; on failure
        the device is looked up again and the call retried once.
        """
        device = self._playback_device()
        try:
            self._sp.start_playback(device_id=device, **kwargs)
        except Exception:
            refreshed = self._playback_device(refresh=True)
            if refreshed == device:
                raise
            self._sp.start_playback(device_id=refreshed, **kwargs)

    @plugs.tag
    def play(self):
        """Resume playback on the configured Spotify device"""
        if not self._require_sp('play'):
            return
        self._claim_active()
        with self._lock:
            try:
                self._start_playback()
            except Exception as e:
                logger.error(f"play(): {e}")
        self._publish_status(state_hint='play')

    @plugs.tag
    def stop(self):
        """Pause Spotify playback"""
        with self._lock:
            try:
                self._sp.pause_playback(device_id=self.device_id)
            except Exception as e:
                logger.error(f"stop(): {e}")
        self._publish_status(state_hint='pause')

    @plugs.tag
    def pause(self, state: int = 1):
        """Pause (state=1) or resume (state=0) playback"""
        if state != 1:
            self._claim_active()
        with self._lock:
            try:
                if state == 1:
                    self._sp.pause_playback(device_id=self.device_id)
                else:
                    self._start_playback()
            except Exception as e:
                logger.error(f"pause(state={state}): {e}")
        self._publish_status(state_hint='pause' if state == 1 else 'play')

    @plugs.tag
    def toggle(self):
        """Toggle between play and pause"""
        self._claim_active()
        new_state = None
        with self._lock:
            try:
                current = self._sp.current_playback()
                if current and current.get('is_playing'):
                    self._sp.pause_playback(device_id=self.device_id)
                    new_state = 'pause'
                else:
                    self._start_playback()
                    new_state = 'play'
            except Exception as e:
                logger.error(f"toggle(): {e}")
        self._publish_status(state_hint=new_state)

    @plugs.tag
    def next(self):
        """Skip to the next track"""
        self._claim_active()
        with self._lock:
            try:
                self._sp.next_track(device_id=self.device_id)
            except Exception as e:
                logger.error(f"next(): {e}")
        self._publish_status()

    @plugs.tag
    def prev(self):
        """Skip to the previous track"""
        self._claim_active()
        with self._lock:
            try:
                self._sp.previous_track(device_id=self.device_id)
            except Exception as e:
                logger.error(f"prev(): {e}")
        self._publish_status()

    @plugs.tag
    def rewind(self):
        """Seek to the beginning of the current track"""
        self._claim_active()
        with self._lock:
            try:
                self._sp.seek_track(0, device_id=self.device_id)
            except Exception as e:
                logger.error(f"rewind(): {e}")
        self._publish_status()

    @plugs.tag
    def seek(self, new_time):
        """Seek to a position in the current track

        :param new_time: position in seconds (matches player.ctrl.seek semantics)
        """
        with self._lock:
            try:
                self._sp.seek_track(int(float(new_time) * 1000), device_id=self.device_id)
            except Exception as e:
                logger.error(f"seek({new_time}): {e}")
        self._publish_status()

    @plugs.tag
    def shuffle(self, option='toggle'):
        """Set shuffle mode: toggle, enable, disable (matches player.ctrl.shuffle semantics)"""
        with self._lock:
            try:
                if option == 'toggle':
                    current = self._sp.current_playback()
                    state = not (current and current.get('shuffle_state'))
                elif option == 'enable':
                    state = True
                elif option == 'disable':
                    state = False
                else:
                    logger.error(f"'{option}' does not exist for 'shuffle'")
                    return
                self._sp.shuffle(state, device_id=self.device_id)
            except Exception as e:
                logger.error(f"shuffle({option}): {e}")
        self._publish_status()

    @plugs.tag
    def repeat(self, option='toggle'):
        """Set repeat mode: cycles off -> repeat (context) -> single (track) -> off

        Accepts the same options as player.ctrl.repeat"""
        with self._lock:
            try:
                current = self._sp.current_playback()
                repeat_state = (current or {}).get('repeat_state', 'off')
                if option == 'toggle':
                    new_mode = {'off': 'context', 'context': 'track', 'track': 'off'}[repeat_state]
                elif option == 'toggle_repeat':
                    new_mode = 'context' if repeat_state == 'off' else 'off'
                elif option == 'toggle_repeat_single':
                    new_mode = 'track' if repeat_state != 'track' else 'off'
                elif option == 'enable_repeat':
                    new_mode = 'context'
                elif option == 'enable_repeat_single':
                    new_mode = 'track'
                elif option == 'disable':
                    new_mode = 'off'
                else:
                    logger.error(f"'{option}' does not exist for 'repeat'")
                    return
                self._sp.repeat(new_mode, device_id=self.device_id)
            except Exception as e:
                logger.error(f"repeat({option}): {e}")
        self._publish_status()

    @plugs.tag
    def play_uri(self, uri: str) -> None:
        """
        Play a Spotify URI directly.

        :param uri: Spotify URI, e.g. 'spotify:playlist:37i9dQZF1DXcBWIGoYBM5M'
                    Supports track, album, and playlist URIs.
        """
        self._claim_active()
        with self._lock:
            try:
                parts = uri.split(':')
                uri_type = parts[1] if len(parts) >= 2 else 'unknown'
                if uri_type == 'track':
                    self._start_playback(uris=[uri])
                else:
                    self._start_playback(context_uri=uri)
                logger.info(f"Playing Spotify URI: {uri}")
            except Exception as e:
                logger.error(f"play_uri('{uri}'): {e}")
        self._publish_status(state_hint='play')

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
        # If another backend (e.g. MPD) played in between, treat as first swipe:
        # the URI needs to be started again, not toggled
        if not components.player.arbiter.is_active('spotify'):
            is_second_swipe = False

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
