# Spotify Merge Completion Design

## Scope

Complete `SPOTIFY_MERGE_TODO.md`, including the optional Spotify album-art enhancement. Preserve existing local scratch files and secrets, verify the merged Spotipy backend and player arbiter, build the webapp locally, then deploy and verify the coherent revision on the Raspberry Pi at `192.168.50.8`.

## Architecture

Spotify remains a Web API control backend and librespot remains the Raspberry Pi playback device. The existing player arbiter continues to own backend selection and transport routing. The change adds missing automated coverage around the merged behavior and extends the normalized `playerstatus` payload with a backend-neutral `albumart` URL.

The web player consumes `albumart` generically. When a backend publishes an image URL, the player uses it directly; otherwise local MPD files continue through the cover-cache RPC. Cover state is cleared when covers are disabled or the current status has no usable image source, preventing stale artwork during backend or track changes.

## Testing

Python tests cover Spotify status normalization, safe image extraction, transport calls, arbiter activation/deactivation, and routing semantics. React tests cover direct remote art, MPD cover-cache fallback, stale-art clearing, and disabled covers. Tests are written before production changes and each focused test must fail for the missing behavior before implementation.

## Deployment

Deploy the complete tested revision rather than only `playerspotify/`, because the merge spans the Spotify backend, arbiter, MPD routing, RPC/configuration, and webapp. Before changing the Pi, derive actual paths and Python environment from the user service definitions and create timestamped backups of code, web build, configuration, token cache, and librespot service definition. Upload through a staging directory, install requirements into the daemon's environment, reload user units, and restart user services.

Automated checks cover service state, logs, listeners, PulseAudio sinks/streams, device resolution, and configuration persistence without printing secrets. OAuth consent, physical RFID swipes, audible playback, and Bluetooth output verification remain user-assisted checks.

## Safety and rollback

Never upload `.env`, local scratch scripts, or token contents. Never replace `jukebox.yaml` with the default template. If deployment verification fails, restore the timestamped code, build, config, token, and service backups, reload user units, restart services, and preserve the failing journal output for diagnosis.
