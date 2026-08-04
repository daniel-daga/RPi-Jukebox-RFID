"""End-to-end Spotify playback tests against a real Mopidy instance.

Mopidy + Mopidy-MPD run for real (from the distro packages); only the
Spotify backend is replaced by a mock that resolves spotify: URIs to a
local silent audio file. The tests speak the MPD protocol - the same
interface mpc and the Phoniebox shell scripts (playout_controls.sh,
rfid_trigger_play.sh) use.
"""

import shutil
import subprocess

import pytest

from conftest import wait_for_state, wait_until
from mpd_client import quote
from php_sandbox import make_php_sandbox


def test_mpd_frontend_is_up(mpd):
    status = mpd.status()
    assert "state" in status
    assert status["playlistlength"] == "0"


def test_add_and_play_spotify_track(mpd):
    """Adding a spotify: URI must resolve through the backend - an
    unresolvable URI would be rejected or queued without metadata."""
    mpd.command(f"add {quote('spotify:track:phonieboxtest1')}")
    entry = mpd.command_dict("playlistinfo")
    assert entry["file"] == "spotify:track:phonieboxtest1"
    # resolved via backend lookup, so the queue carries real metadata
    assert entry.get("title")
    assert entry.get("artist")

    mpd.command("play")
    wait_for_state(mpd, "play")
    wait_until(
        lambda: mpd.command_dict("currentsong").get("file")
        == "spotify:track:phonieboxtest1",
        "the spotify track to become the current song",
    )


def test_spotify_container_uri_expands_to_playable_tracks(mpd):
    """A container URI must be expanded by the backend into individual
    playable tracks rather than queued as a single opaque entry.

    The exact count comes from the mock, so assert the property that
    matters instead: more than one entry, all of them spotify tracks.
    """
    mpd.command(f"add {quote('spotify:album:testalbum123')}")

    files = [
        line.split(": ", 1)[1]
        for line in mpd.command("playlistinfo")
        if line.startswith("file: ")
    ]
    assert len(files) > 1
    assert all(uri.startswith("spotify:track:") for uri in files)


def test_player_controls_pause_play_stop(mpd):
    """The control sequence playout_controls.sh drives via mpc/nc."""
    mpd.command(f"add {quote('spotify:track:controls')}")
    mpd.command("play")
    wait_for_state(mpd, "play")

    mpd.command("pause 1")
    wait_for_state(mpd, "pause")

    mpd.command("pause 0")
    wait_for_state(mpd, "play")

    mpd.command("stop")
    wait_for_state(mpd, "stop")


def test_load_m3u_playlist_with_spotify_uris(mopidy, mpd):
    """rfid_trigger_play.sh writes an .m3u into the playlists folder and
    playout_controls.sh loads it by name ('mpc load <name>')."""
    (mopidy.playlists_dir / "SpotifyTest.m3u").write_text(
        "spotify:track:m3utrack1\nspotify:track:m3utrack2\n"
    )
    mpd.command(f"load {quote('SpotifyTest')}")
    assert mpd.status()["playlistlength"] == "2"

    mpd.command("play")
    wait_for_state(mpd, "play")
    wait_until(
        lambda: mpd.command_dict("currentsong").get("file") == "spotify:track:m3utrack1",
        "the first playlist entry to become the current song",
    )


def test_full_chain_php_playlist_to_mopidy_playback(tmp_path, mopidy, mpd):
    """The full Phoniebox chain without hardware: a folder with a
    spotify.txt -> playlist_recursive_by_folder.php -> .m3u -> MPD load
    -> Mopidy resolves and plays the spotify: URI."""
    if shutil.which("php") is None:
        pytest.skip("php-cli is required for this test")

    sandbox = make_php_sandbox(
        tmp_path, audio_folders_dir=mopidy.audio_folders_dir
    )
    sandbox.add_spotify_folder("KidsAlbum", "spotify:album:fullchain42")

    # what rfid_trigger_play.sh does with the PHP output
    lines = sandbox.playlist("KidsAlbum")
    (mopidy.playlists_dir / "KidsAlbum.m3u").write_text("\n".join(lines) + "\n")

    mpd.command(f"load {quote('KidsAlbum')}")
    # the album URI expands via backend lookup, like real Mopidy-Spotify
    assert mpd.status()["playlistlength"] == "3"

    mpd.command("play")
    wait_for_state(mpd, "play")
    wait_until(
        lambda: mpd.command_dict("currentsong")
        .get("file", "")
        .startswith("spotify:track:fullchain42"),
        "a track of the spotify album to become the current song",
    )


@pytest.mark.skipif(shutil.which("mpc") is None, reason="mpc not installed")
def test_mpc_cli_works_like_the_shell_scripts(mopidy):
    """Drive Mopidy with the actual mpc binary the shell scripts use."""

    def mpc(*args):
        return subprocess.run(
            ["mpc", "-h", "127.0.0.1", "-p", str(mopidy.port), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout

    mpc("clear")
    mpc("add", "spotify:track:mpctest1")
    mpc("play")
    # 'mpc play' returns once the command is acknowledged, the player
    # state follows asynchronously - so poll instead of asserting once
    wait_until(lambda: "[playing]" in mpc("status"), "mpc to report [playing]")
    wait_until(
        lambda: "Mock Spotify Track mpctest1" in mpc("current"),
        "mpc to report the current track",
    )
    mpc("stop")
    mpc("clear")
