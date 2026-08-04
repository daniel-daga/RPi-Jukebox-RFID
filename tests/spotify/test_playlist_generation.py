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
    # exact output: the trailing blank line comes from spotify.txt not
    # being trimmed - see test_untrimmed_spotify_txt_adds_blank_line
    assert (
        sandbox.playlist_raw("SpotifyAlbum")
        == "spotify:album:53m9GKA9GVdKvJEz3asdjS\n\n"
    )


def test_spotify_playlist_uri(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Playlist", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
    assert (
        sandbox.playlist_raw("Playlist")
        == "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M\n\n"
    )


@pytest.mark.xfail(
    strict=True,
    reason="spotify.txt (and livestream.txt) are read with file_get_contents() "
           "and never trimmed, unlike the podcast branch a few lines above, "
           "so a blank line ends up in the generated m3u",
)
def test_untrimmed_spotify_txt_adds_blank_line(tmp_path):
    sandbox = make_php_sandbox(tmp_path)
    sandbox.add_spotify_folder("Trim", "spotify:album:trimme")
    assert sandbox.playlist_raw("Trim") == "spotify:album:trimme\n"


def test_local_files_use_mopidy_local_uris_in_spotify_edition(tmp_path):
    """In the plusSpotify edition local files are addressed via Mopidy-Local
    local:track: URIs with rawurlencoded paths (slashes kept)."""
    sandbox = make_php_sandbox(tmp_path, edition="plusSpotify")
    sandbox.add_local_folder("Alben", ["01 track.mp3", "02.mp3"])
    assert sandbox.playlist_raw("Alben") == (
        "local:track:Alben/01%20track.mp3\n"
        "local:track:Alben/02.mp3\n"
    )


def test_classic_edition_currently_emits_absolute_paths(tmp_path):
    """Documents what the classic branch actually produces today.

    The paired xfail below states what the code says it intends.
    """
    sandbox = make_php_sandbox(tmp_path, edition="classic")
    sandbox.add_local_folder("Alben", ["01 track.mp3"])
    audio = sandbox.audio_folders_dir
    assert sandbox.playlist("Alben") == [f"{audio}/Alben/01 track.mp3"]


@pytest.mark.xfail(
    strict=True,
    reason="The classic branch is commented 'M3U will contain normal relative "
           "path' but emits an absolute one: $folder is already absolute, so "
           "$Audio_Folders_Path.'/'.$folder doubles the prefix and the substr() "
           "strips only one of the two. mpd.conf sets music_directory to the "
           "same folder, so entries are meant to be relative to it.",
)
def test_local_files_should_use_relative_paths_in_classic_edition(tmp_path):
    sandbox = make_php_sandbox(tmp_path, edition="classic")
    sandbox.add_local_folder("Alben", ["01 track.mp3", "02.mp3"])
    assert sandbox.playlist("Alben") == ["Alben/01 track.mp3", "Alben/02.mp3"]


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
