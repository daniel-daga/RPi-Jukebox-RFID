# Spotify Merge Completion Implementation Plan

**Status:** Completed 2026-07-23. See `SPOTIFY_MERGE_STATUS.md` for verification
results and the remaining audible Bluetooth check.

**Goal:** Complete, test, deploy, and verify the Spotipy/librespot merge, including album art.

**Architecture:** Preserve the Spotipy Web API backend and player arbiter. Extend the normalized status with a generic image URL, teach the web player to prefer backend-published art while retaining MPD cover caching, and deploy the entire tested revision coherently.

**Tech Stack:** Python 3, pytest, React 17, Jest/Testing Library, Paramiko, systemd user services, PulseAudio, librespot.

---

### Task 1: Spotify status and album art

**Files:**
- Create: `test/playerspotify/test_player.py`
- Modify: `src/jukebox/components/playerspotify/__init__.py`

1. Add an import-isolated test fixture that constructs `PlayerSpotify` without hardware, timers, OAuth, or network calls.
2. Add failing tests for MPD-compatible status normalization and first-image URL extraction.
3. Add failing tests for missing item, album, images, malformed image entries, stopped state, and transient API errors.
4. Run the focused test and confirm failures are caused by missing `albumart` behavior.
5. Implement minimal safe extraction of a top-level `albumart` string.
6. Run the focused tests and existing `test/playerspotify` tests.
7. Self-review the diff and report commands/results.

### Task 2: Player arbiter and routing coverage

**Files:**
- Create: `test/player/test_arbiter.py`
- Modify only if a demonstrated bug requires it: `src/jukebox/components/player/__init__.py`
- Modify only if a demonstrated bug requires it: `src/jukebox/components/playermpd/__init__.py`

1. Add isolated tests for registration, activation, deactivation, default-backend behavior, missing methods, exceptions, and exactly-once routing.
2. Add an interleaving regression test for MPD -> Spotify -> MPD ownership showing inactive status publishers are suppressed.
3. Run each new test first and distinguish missing coverage from real defects.
4. If a defect is demonstrated, implement only the smallest production fix and rerun the failing test.
5. Run the complete arbiter test file and relevant existing player tests.
6. Self-review the diff and report commands/results.

### Task 3: Web player album-art behavior

**Files:**
- Create: `src/webapp/src/components/Player/index.test.js`
- Modify: `src/webapp/src/components/Player/index.js`

1. Add a React test harness with mocked child components and cover-art request.
2. Add a failing test that uses `playerstatus.albumart` directly without calling MPD cover lookup.
3. Add tests retaining `/cover-cache/<result>` for local files.
4. Add tests for clearing stale art and for `show_covers: false`.
5. Run the focused test and confirm the album-art case fails before production changes.
6. Implement generic precedence: disabled -> clear; published album art -> direct URL; local file -> cover-cache RPC; otherwise -> clear.
7. Include `albumart`, `file`, and `show_covers` in effect dependencies and guard asynchronous stale responses.
8. Run the focused test and webapp build.
9. Keep the current build command unless a reproducible memory failure occurs.
10. Self-review the diff and report commands/results.

### Task 4: Local integration verification

1. Create a project-local Python environment using an available supported interpreter.
2. Install only the dependencies needed for the test suite, adding broader requirements only when a concrete import requires them.
3. Run `pytest test/playerspotify -q` and the arbiter tests.
4. Run the full Python suite and record any environment-only failures separately from regressions.
5. Run the focused React tests and `npm run build` from `src/webapp`.
6. Inspect the full diff and run a final independent code review.

### Task 5: Pi preflight, backup, and deployment

1. Connect with Paramiko to `pi@192.168.50.8`, configuring stdout as UTF-8 with replacement.
2. Read `jukebox-daemon.service` and `librespot.service` to derive deploy paths, Python environment, config path, and web root.
3. Record current service states, librespot version, deployed revision, relevant listeners, PulseAudio sinks, and recent logs.
4. Create timestamped Pi-side backups without reading or printing secret contents.
5. Upload the complete tested revision/web build to staging and atomically replace the deployed files only after transfer succeeds.
6. Install Spotify Python requirements into the daemon's exact environment.
7. Inspect the intended caller for `setup_librespot.inc.sh`; do not execute the include fragment standalone unless it is explicitly self-contained.
8. Reload user units and restart PulseAudio, MPD, librespot, and jukebox daemon in dependency order.
9. Verify all services active, ZMQ listeners present, no new import/OAuth/device errors, and librespot version 0.5 or newer.
10. Roll back from backups if health checks fail.

### Task 6: End-to-end verification and TODO closure

1. Verify Spotify configuration/device selection through RPC or web UI without exposing secrets.
2. Ask the user only for unavoidable OAuth consent/manual redirect completion.
3. Ask the user to swipe a mapped Spotify card and confirm audio, main-player transport, shuffle/repeat, and album art.
4. Verify MPD -> Spotify -> MPD switching in logs/UI and ensure one status owner.
5. Verify selected device survives reload/restart.
6. Ask the user to verify Bluetooth output switching and audible playback.
7. Reboot and repeat one Spotify card test.
8. Update documentation/TODO only with evidence from completed checks; preserve local scratch files and `.env`.
