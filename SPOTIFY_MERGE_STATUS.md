# Spotify Merge Status

Date: 2026-07-23
Branch: codex/spotify-merge-completion

## Completed so far

- Implemented Spotify playback integration from `SPOTIFY_MERGE_TODO.md`.
- Added Spotify album art to backend player status and web UI display paths.
- Added player arbiter ownership so transport commands route to the active backend.
- Added tests for Spotify status ownership, album art propagation, RPC log redaction, and Windows-compatible test behavior.
- Deployed the implementation to the Raspberry Pi at `192.168.50.8` and completed Spotify OAuth using the callback code provided by the user.
- Verified the Pi has an authenticated Spotify token and that the `Phoniebox` Spotify Connect device can be discovered.
- Disabled the older `go-librespot` path and kept `librespot.service` as the playback device.
- Added a hotfix to redact Spotify OAuth authorization codes from future RPC logs.
- Added a hotfix for Spotify Web API `404 Device not found` responses when starting playback by first activating the visible Connect device.
- Added the current follow-up hotfix to retry the activation transfer itself if Spotify lists the device before it accepts the first transfer.

## Verification completed

- Pi-side focused tests passed after the previous hotfix: 47 tests across Spotify/player/RPC log coverage.
- Local focused test calls for the earlier hotfix passed, though the Windows pytest process has intermittently hung after completing output.
- Direct Spotify diagnostic playback on the Pi succeeded after manually transferring playback to the `Phoniebox` device; track metadata and album art were present.
- The daemon and `librespot` service were healthy after the previous deployment.

## Current stuck point

Live RFID-triggered Spotify playback on the Pi is still stuck on Spotify Connect device activation timing.

Observed behavior:

- The Spotify Web API lists the `Phoniebox` device.
- The first `start_playback(device_id=...)` can fail with `404 Device not found`.
- The previous code then tried `transfer_playback(device_id=...)`, but Spotify could return the same `404 Device not found` there too.
- A later direct diagnostic transfer against the same device succeeded and playback worked.

Current hypothesis:

Spotify sometimes exposes the freshly woken or freshly authenticated Connect device through `devices()` before the account is ready to accept a transfer to it. The pending code retries `transfer_playback` once after a short settle delay and refreshes the device ID before retrying `start_playback`.

## Remaining work

- Run the new focused Spotify unit test for the transfer-retry path.
- Deploy the new transfer-retry hotfix to the Pi.
- Scrub the already-consumed OAuth callback code from old daemon logs on the Pi while the daemon is stopped. The application now redacts future calls, but one historical unredacted log line was still present after the earlier deployment.
- Re-run live RFID playlist playback and confirm:
  - backend is `spotify`
  - state becomes `play`
  - title/artist metadata is present
  - album art is present
  - pause routes through the unified player control and leaves playback paused

## Safety notes

- The main workspace was not used for implementation; work happened in the isolated worktree at `C:\tmp\RPi-Jukebox-RFID-spotify-merge`.
- Do not print or copy the old OAuth callback URL/code into logs or documentation. It was one-time and consumed, but it should still be treated as sensitive.
- Preserve `/home/pi/spotify-merge-backups/20260722T223900-f6d2b197` on the Pi as the protected rollback backup.
