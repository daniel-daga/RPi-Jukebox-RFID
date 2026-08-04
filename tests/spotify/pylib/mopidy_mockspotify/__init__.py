"""Mopidy extension that mocks the Spotify backend for CI tests.

Registers the ``spotify:`` URI scheme with Mopidy, exactly like
Mopidy-Spotify does, but resolves every URI to a local silent audio file.
This allows exercising the whole Phoniebox playback chain
(m3u playlist -> mpc/MPD protocol -> Mopidy core -> backend) without
Spotify credentials, network access or ARM hardware.
"""

from mopidy import config, ext

__version__ = "0.1.0"


class Extension(ext.Extension):

    dist_name = "Mopidy-MockSpotify"
    ext_name = "mockspotify"
    version = __version__

    def get_default_config(self):
        return "[mockspotify]\nenabled = true\nmedia_file =\n"

    def get_config_schema(self):
        schema = super().get_config_schema()
        # Local audio file every spotify: URI is resolved to for playback
        schema["media_file"] = config.String(optional=True)
        return schema

    def setup(self, registry):
        from .backend import MockSpotifyBackend

        registry.add("backend", MockSpotifyBackend)
