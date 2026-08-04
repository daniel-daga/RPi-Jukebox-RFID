import pathlib

import pykka
from mopidy import backend
from mopidy.models import Album, Artist, Ref, Track

# Number of tracks a container URI (album/playlist) expands to
CONTAINER_TRACK_COUNT = 3


class MockSpotifyBackend(pykka.ThreadingActor, backend.Backend):

    uri_schemes = ["spotify"]

    def __init__(self, config, audio):
        super().__init__()
        self._config = config["mockspotify"]
        self.library = MockSpotifyLibraryProvider(backend=self)
        self.playback = MockSpotifyPlaybackProvider(audio=audio, backend=self)

    @property
    def media_file(self):
        return self._config.get("media_file") or None


def make_track(uri):
    ident = uri.rsplit(":", 1)[1]
    return Track(
        uri=uri,
        name=f"Mock Spotify Track {ident}",
        artists=frozenset([Artist(name="Mock Artist")]),
        album=Album(name="Mock Album"),
        length=30_000,
    )


class MockSpotifyLibraryProvider(backend.LibraryProvider):

    root_directory = Ref.directory(uri="spotify:directory", name="Mock Spotify")

    def browse(self, uri):
        return []

    def lookup(self, uri):
        if uri.startswith("spotify:track:"):
            return [make_track(uri)]
        # Container URIs expand to several tracks, like the real backend
        if uri.startswith(("spotify:album:", "spotify:playlist:", "spotify:artist:")):
            ident = uri.rsplit(":", 1)[1]
            return [
                make_track(f"spotify:track:{ident}-part{index}")
                for index in range(1, CONTAINER_TRACK_COUNT + 1)
            ]
        return []


class MockSpotifyPlaybackProvider(backend.PlaybackProvider):

    def translate_uri(self, uri):
        media_file = self.backend.media_file
        if not media_file:
            return None
        return pathlib.Path(media_file).absolute().as_uri()
