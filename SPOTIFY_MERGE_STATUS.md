# Spotify Merge Status

Date: 2026-07-23
Branch: future3/develop

## Completed so far

- Implemented Spotify playback integration described in
  `docs/plans/2026-07-21-spotify-merge-completion.md`.
- Added Spotify album art to backend player status and web UI display paths.
- Added player arbiter ownership so transport commands route to the active backend.
- Added tests for Spotify status ownership, album art propagation, RPC log redaction, and Windows-compatible test behavior.
- Deployed the implementation to the Raspberry Pi at `192.168.50.8` and completed Spotify OAuth using the callback code provided by the user.
- Verified the Pi has an authenticated Spotify token and that the `Phoniebox` Spotify Connect device can be discovered.
- Disabled the older `go-librespot` path and kept `librespot.service` as the playback device.
- Added a hotfix to redact Spotify OAuth authorization codes from future RPC logs.
- Added a hotfix for Spotify Web API `404 Device not found` responses when starting playback by first activating the visible Connect device.
- Added the current follow-up hotfix to retry the activation transfer itself if Spotify lists the device before it accepts the first transfer.
- Normalized Spotify's invalid negative progress timeline, including seek re-anchoring and frozen paused/stopped positions.
- Made successful play/pause commands authoritative when Spotify Connect continues to publish stale playback state.
- Added end-of-track detection so the web UI returns to the play icon at the track duration.

## Verification completed

- Pi-side focused Spotify/player/RPC coverage passed: 48 tests after the merge and 21 focused player tests after the live follow-up fixes.
- Live RFID playback starts immediately with backend `spotify`, metadata, and album art.
- Browser-visible seek verification published exactly `30.0` seconds after a routed seek.
- Browser-visible state verification completed for play, pause, resume, and end-of-track stop.
- Paused progress remained fixed at `2.746` seconds across a five-second interval.
- Completed progress remained fixed at `188.186` seconds across a five-second interval.
- The consumed OAuth request is absent from the historical daemon journal, and future request logging is redacted.
- The jukebox daemon, `librespot`, MPD, and PulseAudio services remained active after deployment.

## Current state

The Spotify merge and live player-control follow-ups are complete on `future3/develop` and deployed to the Pi.

The Pi currently uses the temporary silent PulseAudio sink created for visual verification. The Soundcore speaker can be re-paired and selected as the default sink when audible testing is needed again.

## Safety notes

- The main workspace was not used for implementation; work happened in the isolated worktree at `C:\tmp\RPi-Jukebox-RFID-spotify-merge`.
- Do not print or copy the old OAuth callback URL/code into logs or documentation. It was one-time and consumed, but it should still be treated as sensitive.
- Preserve `/home/pi/spotify-merge-backups/20260722T223900-f6d2b197` on the Pi as the protected rollback backup.
