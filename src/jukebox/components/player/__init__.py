import os
import re
import logging
import threading
import jukebox.cfghandler
from typing import Optional


logger = logging.getLogger('jb.player')
cfg = jukebox.cfghandler.get_handler('jukebox')


def _get_music_library_path(conf_file):
    """Parse the music directory from the mpd.conf file"""
    pattern = re.compile(r'^\s*music_directory\s*"(.*)"', re.I)
    directory = None
    with open(conf_file, 'r') as f:
        for line in f:
            res = pattern.match(line)
            if res:
                directory = res.group(1)
                break
        else:
            logger.error(f"Could not find music library path in {conf_file}")
    logger.debug(f"MPD music lib path = {directory}; from {conf_file}")
    return directory


class MusicLibPath:
    """Extract the music directory from the mpd.conf file"""
    def __init__(self):
        self._music_library_path = None
        mpd_conf_file = cfg.setndefault('playermpd', 'mpd_conf', value='~/.config/mpd/mpd.conf')
        try:
            self._music_library_path = _get_music_library_path(os.path.expanduser(mpd_conf_file))
        except Exception as e:
            logger.error(f"Could not determine music library directory from '{mpd_conf_file}'")
            logger.error(f"Reason: {e.__class__.__name__}: {e}")

    @property
    def music_library_path(self):
        return self._music_library_path


# ---------------------------------------------------------------------------
# Unified playback engine: the player arbiter
# ---------------------------------------------------------------------------


class PlayerArbiter:
    """Coordinates multiple player backends (MPD, Spotify, ...) as one unified player

    Exactly one backend is *active* at any time. A backend claims the active
    slot right before it starts playback; the arbiter then silences every
    other backend, so two backends never play at the same time.

    The active backend

    * receives the transport commands issued to ``player.ctrl.*``
      (webapp, RFID cards, GPIO) — see :func:`route_from_default`
    * owns the shared ``playerstatus`` publishing topic — backends must
      check :func:`is_active` before publishing

    Backends register with :func:`register_backend` and are duck-typed: they
    provide the transport methods that shall be routable (``play``, ``pause``,
    ``toggle``, ``next``, ``prev``, ``seek``, ``rewind``, ``stop``, ...) plus
    ``on_deactivate()``, which must silence the backend without routing back
    through the arbiter.
    """

    # The backend behind player.ctrl.*; it needs no routing to be reached
    DEFAULT_BACKEND = 'mpd'

    def __init__(self):
        self._lock = threading.RLock()
        self._backends = {}
        self._active_name: Optional[str] = None

    def register_backend(self, name: str, backend) -> None:
        with self._lock:
            self._backends[name] = backend
        logger.info(f"Player backend registered: '{name}'")

    @property
    def active_name(self) -> str:
        with self._lock:
            return self._active_name or self.DEFAULT_BACKEND

    def is_active(self, name: str) -> bool:
        return self.active_name == name

    def claim_active(self, name: str) -> None:
        """Make backend `name` the active player and silence all others

        Backends call this right before they start making sound."""
        with self._lock:
            if self._active_name == name:
                return
            previous = self._active_name or self.DEFAULT_BACKEND
            self._active_name = name
            others = [(n, b) for n, b in self._backends.items() if n != name]
        logger.info(f"Active player backend: '{previous}' -> '{name}'")
        for other_name, other in others:
            try:
                other.on_deactivate()
            except Exception as e:
                logger.error(f"Silencing player backend '{other_name}' failed: {e.__class__.__name__}: {e}")

    def route_from_default(self, method: str, *args, **kwargs):
        """Forward a transport command to the active backend if that is not the default

        The default backend (playermpd, reachable as ``player.ctrl``) calls this
        at the top of each transport method, so ``player.ctrl.*`` remains the
        single entry point for the webapp, RFID cards and GPIO no matter which
        backend is playing.

        :return: Tuple (handled, result). When handled is True the command was
            consumed by the active backend and the caller must not additionally
            execute it on the default backend.
        """
        with self._lock:
            name = self._active_name
            backend = self._backends.get(name)
        if name is None or name == self.DEFAULT_BACKEND or backend is None:
            return False, None
        func = getattr(backend, method, None)
        if func is None:
            logger.warning(f"Active player backend '{name}' does not support '{method}' - command ignored")
            return True, None
        try:
            return True, func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Routing '{method}' to active player backend '{name}' failed: "
                         f"{e.__class__.__name__}: {e}")
            return True, None


arbiter = PlayerArbiter()


# ---------------------------------------------------------------------------


_MUSIC_LIBRARY_PATH: Optional[MusicLibPath] = None


def get_music_library_path():
    """Get the music library path"""
    global _MUSIC_LIBRARY_PATH
    if _MUSIC_LIBRARY_PATH is None:
        _MUSIC_LIBRARY_PATH = MusicLibPath()
    return _MUSIC_LIBRARY_PATH.music_library_path
