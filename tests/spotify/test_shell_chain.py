"""End-to-end tests that execute the real Phoniebox shell scripts.

Unlike the other playback tests, these do not reimplement what
rfid_trigger_play.sh does - they run it. That covers the parts which are
pure shell logic and were previously untested: the playlist name
encoding (slashes become ' % '), the RFID shortcut lookup, and the
handover to playout_controls.sh / resume_play.sh.
"""

from conftest import wait_for_state, wait_until


def queue_files(mpd):
    return [
        line.split(": ", 1)[1]
        for line in mpd.command("playlistinfo")
        if line.startswith("file: ")
    ]


def test_trigger_play_subfolder_builds_encoded_playlist(phoniebox, mpd):
    """A folder containing a slash must end up as a ' % ' playlist name,
    because slashes cannot appear in an MPD playlist name."""
    phoniebox.add_spotify_folder("Master/Sub1", "spotify:album:shelltest99")

    result = phoniebox.trigger_play("-d=Master/Sub1")
    assert result.returncode == 0, result.stderr

    assert phoniebox.playlist_file("Master % Sub1").is_file()

    wait_until(lambda: queue_files(mpd), "the queue to be filled by the script")
    assert queue_files(mpd) == [
        "spotify:track:shelltest99-part1",
        "spotify:track:shelltest99-part2",
        "spotify:track:shelltest99-part3",
    ]
    wait_for_state(mpd, "play")


def test_trigger_play_flat_folder(phoniebox, mpd):
    phoniebox.add_spotify_folder("Hoerspiel", "spotify:playlist:shellflat1")

    result = phoniebox.trigger_play("-d=Hoerspiel")
    assert result.returncode == 0, result.stderr

    assert phoniebox.playlist_file("Hoerspiel").is_file()
    wait_until(lambda: queue_files(mpd), "the queue to be filled by the script")
    assert all(uri.startswith("spotify:track:shellflat1") for uri in queue_files(mpd))


def test_trigger_play_by_card_id_uses_shortcut(phoniebox, mpd):
    """The RFID path: a card ID is resolved via shared/shortcuts."""
    phoniebox.add_spotify_folder("Lieblingsalbum", "spotify:album:shellcard7")
    phoniebox.add_shortcut("0009999999", "Lieblingsalbum")

    result = phoniebox.trigger_play("-i=0009999999")
    assert result.returncode == 0, result.stderr

    wait_until(lambda: queue_files(mpd), "the queue to be filled by the script")
    assert all(uri.startswith("spotify:track:shellcard7") for uri in queue_files(mpd))


def test_trigger_play_records_latest_playlist(phoniebox, mpd):
    """rfid_trigger_play.sh remembers the playlist so a second swipe can
    be recognised - the settings file must match the encoded name."""
    phoniebox.add_spotify_folder("Master/Sub2", "spotify:album:shelllatest")

    phoniebox.trigger_play("-d=Master/Sub2")

    latest = (phoniebox.root / "settings" / "Latest_Playlist_Played").read_text()
    assert latest.strip() == "Master % Sub2"


def test_bootstraps_global_conf_when_missing(phoniebox_factory, mpd):
    """On a box without settings/global.conf (first run after a fresh
    checkout) the script has to create it and still play.

    It is invoked by systemd and by the web UI, so it cannot rely on the
    caller's working directory being scripts/.
    """
    phoniebox = phoniebox_factory(write_global_conf=False)
    global_conf = phoniebox.root / "settings" / "global.conf"
    assert not global_conf.exists()

    phoniebox.add_spotify_folder("Bootstrap", "spotify:album:bootstrap1")
    result = phoniebox.trigger_play("-d=Bootstrap")

    assert "inc.writeGlobalConfig.sh: No such file" not in result.stderr, (
        "the include was not resolved relative to the script location"
    )
    assert global_conf.is_file(), "global.conf was not created"
    wait_until(lambda: queue_files(mpd), "the queue to be filled by the script")


def test_resume_play_bootstraps_global_conf_when_missing(phoniebox_factory):
    """resume_play.sh carries the same bootstrap block."""
    phoniebox = phoniebox_factory(write_global_conf=False)
    global_conf = phoniebox.root / "settings" / "global.conf"
    phoniebox.add_spotify_folder("ResumeBootstrap", "spotify:album:resume1")

    result = phoniebox.run("resume_play.sh", "-c=resume", "-d=ResumeBootstrap")

    assert "inc.writeGlobalConfig.sh: No such file" not in result.stderr, (
        "the include was not resolved relative to the script location"
    )
    assert global_conf.is_file(), "global.conf was not created"


def test_generated_m3u_is_written_verbatim(phoniebox):
    """The m3u on disk is exactly what the PHP generator emitted."""
    phoniebox.add_spotify_folder("Blankline", "spotify:album:shellblank")
    phoniebox.trigger_play("-d=Blankline")

    content = phoniebox.playlist_file("Blankline").read_text()
    assert content == "spotify:album:shellblank\n"
