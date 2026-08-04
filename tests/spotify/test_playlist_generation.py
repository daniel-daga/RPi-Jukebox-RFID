"""Tests for spotify (and plusSpotify edition) playlist generation.

Runs the real scripts/playlist_recursive_by_folder.php (the script
rfid_trigger_play.sh uses to build the .m3u that is handed to
Mopidy/MPD) against sandboxed audio folders.
"""

import shutil

import pytest

from php_sandbox import make_php_sandbox

pytestmark = pytest.mark.skipif(
    shutil.which("php") is None, reason="php-cli is required for these tests"
)


def test_spotify_folder_yields_spotify_uri(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("SpotifyAlbum", "spotify:album:53m9GKA9GVdKvJEz3asdjS")
    assert (
        sandbox.playlist_raw("SpotifyAlbum")
        == "spotify:album:53m9GKA9GVdKvJEz3asdjS\n"
    )


def test_spotify_playlist_uri(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Playlist", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
    assert (
        sandbox.playlist_raw("Playlist") == "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M\n"
    )


def test_spotify_txt_is_trimmed(tmp_path):
    """The URI must not carry the file's trailing newline into the m3u."""
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Trim", "spotify:album:trimme")
    assert sandbox.playlist_raw("Trim") == "spotify:album:trimme\n"


def test_spotify_txt_with_windows_line_ending_is_trimmed(tmp_path):
    """Audio folders are edited over the Samba share, so a spotify.txt
    saved on Windows arrives with CRLF."""
    sandbox = make_php_sandbox(tmp_path)
    sandbox.write_uri_file("CRLF", "spotify.txt", "spotify:album:crlf42\r\n")
    assert sandbox.playlist_raw("CRLF") == "spotify:album:crlf42\n"


def test_livestream_txt_is_trimmed(tmp_path):
    """Same untrimmed read as spotify.txt, one branch above."""
    sandbox = make_php_sandbox(tmp_path)
    sandbox.write_uri_file("Radio", "livestream.txt", "http://stream.example/live\n")
    assert sandbox.playlist_raw("Radio") == "http://stream.example/live\n"


def test_local_files_use_mopidy_local_uris_in_spotify_edition(tmp_path):
    """In the plusSpotify edition local files are addressed via Mopidy-Local
    local:track: URIs with rawurlencoded paths (slashes kept)."""
    sandbox = make_php_sandbox(tmp_path, edition="plusSpotify")
    sandbox.add_local_folder("Alben", ["01 track.mp3", "02.mp3"])
    assert sandbox.playlist_raw("Alben") == (
        "local:track:Alben/01%20track.mp3\n"
        "local:track:Alben/02.mp3\n"
    )


def test_local_files_use_relative_paths_in_classic_edition(tmp_path):
    """mpd.conf sets music_directory to the audio folders dir, so classic
    edition entries have to be relative to it."""
    sandbox = make_php_sandbox(tmp_path, edition="classic")
    sandbox.add_local_folder("Alben", ["01 track.mp3", "02.mp3"])
    assert sandbox.playlist_raw("Alben") == (
        "Alben/01 track.mp3\n"
        "Alben/02.mp3\n"
    )


def test_classic_edition_paths_stay_relative_in_subfolders(tmp_path):
    """The doubled-prefix bug was invisible at the top level of the audio
    folder but produced a wrong prefix for nested folders too."""
    sandbox = make_php_sandbox(tmp_path, edition="classic")
    sandbox.add_local_folder("Master/Sub", ["track.mp3"])
    assert sandbox.playlist("Master/Sub") == ["Master/Sub/track.mp3"]


def test_helper_files_are_excluded(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_local_folder(
        "Mixed",
        ["01.mp3", "folder.conf", "cover.jpg", "title.txt", "list.m3u", "img.png", ".hidden"],
    )
    assert sandbox.playlist("Mixed") == ["local:track:Mixed/01.mp3"]


def test_recursive_playlist_mixes_spotify_and_local(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Master/Sub1", "spotify:album:abc123")
    sandbox.add_local_folder("Master/Sub2", ["track.mp3"])
    lines = sandbox.playlist("Master", recursive=True)
    assert lines == [
        "spotify:album:abc123",
        "local:track:Master/Sub2/track.mp3",
    ]


def test_subfolder_can_be_played_directly(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Master/Sub1", "spotify:album:abc123")
    assert sandbox.playlist("Master/Sub1") == ["spotify:album:abc123"]
