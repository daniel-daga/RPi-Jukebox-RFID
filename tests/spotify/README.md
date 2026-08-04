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

The Phoniebox chain is then driven from both ends:

```text
folder with spotify.txt
  -> scripts/rfid_trigger_play.sh        (really executed, test_shell_chain.py)
  -> playlist_recursive_by_folder.php    (really executed, via php-cli)
  -> .m3u in the playlists dir
  -> scripts/playout_controls.sh -> mpc / resume_play.sh
  -> Mopidy core -> spotify: backend lookup & playback
```

`test_shell_chain.py` runs the actual shell scripts, so the pure-shell
logic is covered too: the playlist name encoding (slashes become ` % `),
the RFID shortcut lookup, and the handover to `playout_controls.sh`.
Because those scripts talk to `localhost 6600` hardcoded, they are only
exercised when the test instance owns the standard MPD port; if it is
taken, those tests skip with a message instead of silently passing.

`test_playback.py` drives the same player over the MPD protocol directly
and is closer to a harness/integration smoke test - several of its
assertions describe the mock, not Phoniebox.

## What is covered

- `test_mopidy_config.py` - the installer's `mopidy.conf` generation
  (same `sed` + `escape_for_sed` logic as `install-jukebox.sh`),
  including credentials full of special characters. Mopidy boots from
  the generated config, so a malformed `[local]`, `[file]`, `[m3u]`,
  `[mpd]` or `[http]` section fails the run.
- `test_playlist_generation.py` - `playlist_recursive_by_folder.php`:
  `spotify.txt` folders, `local:track:` URI encoding in the plusSpotify
  edition, classic edition paths, helper-file exclusion, recursive
  playlists mixing Spotify and local content. Assertions compare the
  generator's exact output, because the m3u is written to disk verbatim.
- `test_shell_chain.py` - `rfid_trigger_play.sh` end to end: playlist
  name encoding, card-ID shortcuts, `Latest_Playlist_Played` bookkeeping.
- `test_playback.py` - MPD-protocol level: playing `spotify:` URIs,
  container URI expansion, the pause/play/stop sequences
  `playout_controls.sh` uses, loading `.m3u` playlists by name, and a
  smoke test through the real `mpc` binary.

### Known defects recorded as xfail

Two `xfail(strict=True)` tests state intended behaviour that the code
does not currently deliver. They fail the suite if the behaviour is
fixed, as a prompt to remove the marker:

- `spotify.txt` is read with `file_get_contents()` and never trimmed
  (unlike the podcast branch), so a blank line lands in the generated
  m3u. Harmless for Mopidy today.
- The classic-edition branch is commented "M3U will contain normal
  relative path" but emits an absolute one, because `$folder` is already
  absolute and the `substr()` strips only one of the two prefixes.

### Not covered

- Real Mopidy-Spotify authentication and streaming - needs valid
  credentials and network; that is Mopidy-Spotify's own test scope.
- ALSA audio output - hardware-specific; playback runs against a
  real-time fake sink.
- The `[iris]` config section - Mopidy-Iris is pip-only and not
  installed here, so Mopidy ignores that section.
- `playout_controls.sh` beyond the play path (volume, shutdown, wifi,
  bluetooth, recording).

## Running locally

```bash
sudo apt-get install mopidy mopidy-mpd mopidy-local mpc \
    gstreamer1.0-plugins-good php-cli netcat-openbsd python3-pytest
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
