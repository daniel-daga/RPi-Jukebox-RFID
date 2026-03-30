# Spotify Integration — Developer Notes

## Overview

The Spotify integration adds a `playerspotify` plugin that allows RFID cards to trigger
Spotify playback (tracks, albums, playlists) alongside the existing MPD local-music player.
Both players coexist — local music via MPD and Spotify run independently.

**Requirements:**
- Spotify Premium account
- Spotify Developer App (free, created at developer.spotify.com)
- `spotipy` Python library (`pip install spotipy`)

---

## File Map

### Backend

| Path | Purpose |
|------|---------|
| `src/jukebox/components/playerspotify/__init__.py` | Main plugin — OAuth server, playback control, RPC methods |
| `src/jukebox/components/playerspotify/requirements.txt` | Python dependency: `spotipy>=2.23.0` |
| `resources/default-settings/jukebox.default.yaml` | Commented-out `playerspotify:` config block (reference) |
| `resources/default-settings/cards.example.yaml` | Commented-out Spotify card examples |

### Frontend (webapp)

| Path | Purpose |
|------|---------|
| `src/webapp/src/components/Settings/spotify/index.js` | Settings card container |
| `src/webapp/src/components/Settings/spotify/connect.js` | Auth status, Connect/Disconnect button, polling |
| `src/webapp/src/components/Settings/spotify/device-select.js` | Spotify Connect device picker |
| `src/webapp/src/components/Settings/spotify/second-swipe.js` | Second-swipe action radio group |
| `src/webapp/src/components/Settings/index.js` | Modified — imports and renders `SettingsSpotify` |
| `src/webapp/src/commands/index.js` | Modified — added 7 Spotify RPC command mappings |
| `src/webapp/public/locales/en/translation.json` | Modified — added `settings.spotify.*` keys |
| `src/webapp/public/locales/de/translation.json` | Modified — added German translations |

---

## Architecture

### Plugin Registration

The plugin registers under the `spotify` package name (not `player`), so it coexists with MPD:

```yaml
# jukebox.yaml — modules.named
spotify: playerspotify   # add this line
player: playermpd        # keeps working as before
```

Inside the plugin:
```python
plugs.register(player_ctrl, name='ctrl')
# Accessible as: spotify.ctrl.<method>
```

### OAuth Flow (built-in, no separate script)

1. On startup, if no token is cached, the plugin starts a temporary `HTTPServer` on port 8888
   in a daemon thread.
2. The UI calls `get_auth_url()` → returns the Spotify authorization URL.
3. User opens the URL in a browser, logs in, Spotify redirects to
   `http://<pi>:8888/callback?code=XYZ`.
4. The callback handler receives the code, calls `auth_manager.get_access_token(code)`,
   saves the token to `token_cache`, and shuts the server down.
5. The UI polls `get_auth_status()` every 3 seconds and shows "Connected as …" when done.

The callback server port is derived from the `redirect_uri` config value — so changing the
port in the Spotify App and in config is enough; no code changes needed.

### Card → Playback Flow

```
RFID swipe
  └─▶ cards.yaml lookup → { package: spotify, plugin: ctrl, method: play_card, args: [uri] }
        └─▶ spotify.ctrl.play_card(uri)
              ├─ first swipe  → play_uri(uri)  [stores uri as last_played_uri]
              └─ second swipe → second_swipe_action()  [toggle / play / skip / rewind / none]
```

`last_played_uri` is stored in `shared/settings/spotify_player_status.json` (via `nv_manager`),
same pattern as MPD's `music_player_status.json`.

### Device Selection

- `device_id = None` (default) → Spotify plays on whichever device is currently active.
- Set a specific device via Settings UI → saved to `spotify_player_status.json`.
- For the Pi to be the playback device itself, install **raspotify**:
  ```bash
  curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
  ```
  Then open Spotify on any device, the Pi appears as a Connect device named "Raspotify".

---

## Configuration

Add to `jukebox.yaml` (your local override, not the default file):

```yaml
modules:
  named:
    # ... existing entries ...
    spotify: playerspotify

playerspotify:
  client_id: YOUR_CLIENT_ID
  client_secret: YOUR_CLIENT_SECRET
  # Must match exactly what you set in the Spotify Developer App:
  redirect_uri: http://<your-pi-hostname-or-ip>:8888/callback
  token_cache: ../../shared/settings/.spotify_token
  status_file: ../../shared/settings/spotify_player_status.json
  # device_id: leave empty to use the active device, or set a specific ID
  device_id:
  second_swipe_action:
    alias: toggle   # toggle | play | skip | rewind | none
```

---

## Setup (step by step)

1. **Create a Spotify Developer App**
   - Go to https://developer.spotify.com/dashboard
   - Create an app (any name/description)
   - Under *Settings → Redirect URIs* add:
     `http://<your-pi-hostname-or-ip>:8888/callback`
   - Copy the **Client ID** and **Client Secret**

2. **Install the Python dependency** (on the Pi)
   ```bash
   pip install spotipy>=2.23.0
   ```

3. **Edit `jukebox.yaml`** — add the `playerspotify` block and module entry shown above.

4. **Restart the jukebox**
   ```bash
   systemctl restart jukebox   # or however you run it
   ```

5. **Authorise** — open the web UI → Settings → Spotify → click **Connect with Spotify**.
   A browser tab opens; log in and approve. The UI auto-updates to "Connected as …".

6. **Pick a device** — in the same settings card, click *Refresh*, select the device,
   click *Save*.

7. **Map cards** — add entries to `shared/settings/cards.yaml`:
   ```yaml
   '0123456789':
     package: spotify
     plugin: ctrl
     method: play_card
     args: ['spotify:playlist:37i9dQZF1DXcBWIGoYBM5M']
   ```
   Get the URI from Spotify: right-click any track/album/playlist → *Share* → *Copy URI*.

---

## RPC Methods (spotify.ctrl)

| Method | Args | Description |
|--------|------|-------------|
| `play_card` | `uri: str` | Main RFID entry point — first/second swipe logic |
| `play_uri` | `uri: str` | Play a Spotify URI directly (no swipe logic) |
| `play` | — | Resume playback |
| `stop` | — | Pause playback |
| `pause` | `state: int` | Pause (1) or resume (0) |
| `toggle` | — | Toggle play/pause |
| `next` | — | Next track |
| `prev` | — | Previous track |
| `rewind` | — | Seek to start of current track |
| `playerstatus` | — | Returns state, title, artist, album, progress, volume |
| `list_devices` | — | Returns list of available Spotify Connect devices |
| `get_auth_status` | — | Returns `{ authenticated, auth_in_progress, user, email }` |
| `get_auth_url` | — | Returns the Spotify OAuth URL; starts callback server |
| `disconnect` | — | Deletes cached token, restarts callback server |
| `set_device` | `device_id` | Persists chosen device (pass `null` for active device) |
| `get_second_swipe_action` | — | Returns current action name string |
| `set_second_swipe_action` | `action: str` | Sets action: toggle / play / skip / rewind / none |

---

## Known Limitations & Future Work

- **No webapp player integration** — Spotify status is not shown in the main player UI,
  only in the Settings panel. A future addition could publish playback state to the
  pub/sub system so the player screen can display the current Spotify track.
- **Token expiry** — spotipy handles refresh automatically as long as a refresh token
  exists. If the refresh token ever expires (rare), the user must re-authorise via the UI.
- **Single device** — the plugin targets one device at a time. Switching devices mid-session
  requires going to Settings.
- **No shuffle/repeat from UI** — `shuffle` and `repeat` are not yet wired for Spotify
  (Spotify's API supports them; just not implemented yet).
- **raspotify recommended** — without raspotify, Spotify must be open on some other device
  for playback to work. With raspotify the Pi itself is the speaker.
