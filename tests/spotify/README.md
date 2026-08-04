# Spotify feature tests (no Raspberry Pi required)

Fast, deterministic tests for the Phoniebox Spotify (+Spotify edition)
functionality that run on any Linux machine or plain CI runner - no
Raspberry Pi, no QEMU, no Spotify account/credentials and no downloads
from `apt.mopidy.com` or GitHub releases.

They complement `scripts/installscripts/tests/run_installation_spotify.sh`
(the full installation run inside a Docker/QEMU container): the
installation test verifies *installing* the Spotify edition, while these
tests verify that the Spotify *feature logic* keeps working - in seconds
instead of tens of minutes, and without depending on external package
mirrors at test time.

## How it works

A real Mopidy instance with the real Mopidy-MPD frontend is started
(both installed from the regular distro archive). Only the Spotify
backend is swapped for a mock: `pylib/mopidy_mockspotify` is a tiny
Mopidy extension that registers the `spotify:` URI scheme - exactly like
Mopidy-Spotify does - and resolves every URI to a local silent audio
file. Container URIs (`spotify:album:...`, `spotify:playlist:...`)
expand to several tracks, like with the real backend.

That means the whole Phoniebox chain runs unmodified:

```text
folder with spotify.txt
  -> scripts/playlist_recursive_by_folder.php  (real, via php-cli)
  -> .m3u in the playlists dir                 (like rfid_trigger_play.sh)
  -> MPD protocol 'load' / 'play' / 'pause'    (like playout_controls.sh / mpc)
  -> Mopidy core -> spotify: backend lookup & playback
```

## What is covered

- `test_mopidy_config.py` - the installer's `mopidy.conf` generation
  (same `sed` + `escape_for_sed` logic as `install-jukebox.sh`),
  including credentials full of special characters. The generated config
  is also the one the Mopidy test instance boots with.
- `test_playlist_generation.py` - `playlist_recursive_by_folder.php`:
  `spotify.txt` folders, `local:track:` URI encoding in the plusSpotify
  edition, classic edition paths, helper-file exclusion, recursive
  playlists mixing Spotify and local content.
- `test_playback.py` - end-to-end against the running Mopidy: adding and
  playing `spotify:` URIs over the MPD protocol, album expansion, the
  pause/play/stop sequences `playout_controls.sh` uses, loading `.m3u`
  playlists by name, the full PHP-to-playback chain, and a smoke test
  through the real `mpc` binary.

What is intentionally *not* covered: the real Mopidy-Spotify
authentication and streaming (needs valid credentials and network;
that is Mopidy-Spotify's own test scope) and ALSA audio output
(hardware-specific; playback runs against a real-time fake sink).

## Running locally

```bash
sudo apt-get install mopidy mopidy-mpd mpc gstreamer1.0-plugins-good php-cli python3-pytest
./tests/spotify/run_tests.sh
```

If the python interpreter that has the distro mopidy packages is not
auto-detected (e.g. because `python3` points to a custom build), set it
explicitly:

```bash
MOPIDY_PYTHON=/usr/bin/python3 ./tests/spotify/run_tests.sh
```

CI runs this via `.github/workflows/test_spotify.yml` on a plain
`ubuntu-latest` runner.
