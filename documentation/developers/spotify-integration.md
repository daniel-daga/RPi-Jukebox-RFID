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
| `src/jukebox/components/playerspotify/auth_code.py` | Pure helper — extracts the OAuth code from a pasted redirect URL |
| `src/jukebox/components/playerspotify/requirements.txt` | Python dependency: `spotipy>=2.23.0` |
| `resources/default-settings/jukebox.default.yaml` | Commented-out `playerspotify:` config block (reference) |
| `resources/default-settings/cards.example.yaml` | Commented-out Spotify card examples |

### Frontend (webapp)

| Path | Purpose |
|------|---------|
| `src/webapp/src/components/Settings/spotify/index.js` | Settings card container — owns auth status, switches wizard ↔ settings view |
| `src/webapp/src/components/Settings/spotify/wizard.js` | Guided first-time setup (stepper): create app → credentials → connect |
| `src/webapp/src/components/Settings/spotify/utils.js` | Redirect-URI helpers (suggested Pi URI, loopback fallback) |
| `src/webapp/src/components/Settings/spotify/credentials.js` | Client ID/Secret form, prefills the redirect URI |
| `src/webapp/src/components/Settings/spotify/connect.js` | Auth status, Connect/Disconnect button, manual code-paste fallback |
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

**Manual fallback (`submit_auth_code`):** Spotify's dashboard only accepts plain-HTTP
redirect URIs for loopback addresses (`http://127.0.0.1:...`), so for newly created apps
the redirect may land on the *user's* machine instead of the Pi and show an error page.
In that case the user copies the full address (`...callback?code=XYZ`) from the browser
and pastes it into the connect step of the web UI; `submit_auth_code()` extracts the code
(see `auth_code.py`) and completes the token exchange.

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

The whole setup runs from the web UI. Open **Settings → Spotify** — until the account is
connected, a guided wizard walks through all steps:

1. **Create a Spotify Developer App** — the wizard links to
   https://developer.spotify.com/dashboard and shows the exact Redirect URI to add,
   derived from the address the web UI is opened on (with a copy button). If Spotify's
   dashboard rejects that address (plain HTTP is only accepted for loopback), the wizard
   offers `http://127.0.0.1:8888/callback` as the alternative.

2. **Enter credentials** — paste the app's **Client ID** and **Client Secret**; the
   Redirect URI is prefilled. Saving reinitialises the plugin, no restart needed.

3. **Connect** — click **Connect with Spotify**, log in and approve in the opened tab.
   The UI auto-updates to "Connected as …". If the redirect could not reach the Pi
   (loopback URI), copy the error page's address (`...?code=...`) into the paste field
   shown below the button.

Once connected, the card switches to the regular settings (device, second-swipe action).

4. **Pick a device** *(optional)* — by default playback goes to the librespot instance
   on the Pi itself (device name `Phoniebox`). Select a different Spotify Connect device
   under *Playback Device* if desired.

5. **Map cards** — either via the Cards UI (action *Spotify*) or in
   `shared/settings/cards.yaml`:
   ```yaml
   '0123456789':
     package: spotify
     plugin: ctrl
     method: play_card
     args: ['spotify:playlist:37i9dQZF1DXcBWIGoYBM5M']
   ```
   Get the URI from Spotify: right-click any track/album/playlist → *Share* → *Copy URI*.

The module ships enabled in `jukebox.default.yaml` (`spotify: playerspotify` under
`modules.named`); `spotipy` and librespot are installed by
`src/jukebox/components/playerspotify/setup.inc.sh`.

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
| `submit_auth_code` | `code_or_url: str` | Completes OAuth with a manually pasted redirect URL or code |
| `disconnect` | — | Deletes cached token, restarts callback server |
| `set_device` | `device_id` | Persists chosen device (pass `null` for active device) |
| `get_second_swipe_action` | — | Returns current action name string |
| `set_second_swipe_action` | `action: str` | Sets action: toggle / play / skip / rewind / none |

---

## Unified playback engine

MPD and Spotify are coordinated by the *player arbiter*
(`components.player.PlayerArbiter`): exactly one backend is the **active player**
at any time. A backend claims the active slot right before it starts playback
(`play_card`, `play_uri`, `play_folder`, ...); the arbiter then silences the other
backend, so the two never play simultaneously.

Consequences:

- **One entry point** — the webapp, RFID cards and GPIO keep calling
  `player.ctrl.*`. While Spotify is the active player, the transport commands
  (`play`, `pause`, `toggle`, `next`, `prev`, `seek`, `rewind`, `stop`, `shuffle`,
  `repeat`) are routed to `spotify.ctrl.*` automatically
  (see `route_to_active_player` in `playermpd`).
- **One status topic** — the active backend owns the `playerstatus` pub/sub topic.
  Spotify publishes a normalized, MPD-compatible payload (`state`, `songid`,
  `title`, `artist`, `album`, `elapsed`, `duration`, `random`, `repeat`, `single`,
  plus `player: spotify`), so the main player screen shows and controls whatever
  is playing. Immediately after each transport command the fresh state is
  published; a 2 s poll keeps it in sync while playing.
- **Second swipe stays intuitive** — when the other backend played in between,
  a card swipe counts as first swipe again (playback restarts instead of toggling).

## Automated testing without a Raspberry Pi

The Spotify integration is fully autotestable on any machine — no Pi, no
network, no Spotify account. Two complementary layers live in
`test/playerspotify/`:

- **Unit tests** (`test_player.py`, `test_auth_code.py`, `test_device_resolver.py`,
  `test_librespot_seeder.py`) — isolated checks of individual methods with
  `unittest.mock`.
- **Scenario tests** (`test_spotify_scenarios.py`) — end-to-end flows against a
  **stateful Spotify Web API emulator** (`fake_spotify.py`). The harness
  (`conftest.py`, fixtures `spotify_env` / `make_spotify_env`) boots the *real*
  code — the full `PlayerSpotify` constructor, the real player arbiter
  (`components.player`), `NvManager`, `device_resolver` — and fakes only the
  true boundaries: the Web API, OAuth, the ZMQ publisher, the status poll
  timer, and wall-clock time.

`FakeSpotify` simulates a Spotify Connect account: a music catalog
(tracks/albums/playlists), Connect devices, and a playback session whose
progress advances on a deterministic fake clock (`env.clock.advance(5)` moves
playback 5 s forward, instantly). It also reproduces the Connect quirks the
plugin has to handle, so the retry/normalization logic is exercised against
realistic behaviour instead of canned mock returns:

- a freshly seeded librespot device that is listed but rejects playback until
  a transfer activates it (`needs_activation`, `rejected_transfers`)
- stale device ids after a librespot restart (`remove_device` + `add_device`)
- the negative-progress timeline bug (`progress_offset_ms`)

A typical scenario reads like the user story it verifies:

```python
def test_second_swipe_toggles(spotify_env):
    env = spotify_env
    env.player.play_card(env.playlist_uri)   # first swipe -> plays
    env.clock.advance(10)
    env.player.play_card(env.playlist_uri)   # second swipe -> pauses
    assert not env.spotify.is_playing
    assert env.last_status()['state'] == 'pause'
```

Run with `pytest test/playerspotify` (plain `pytest` is enough — the harness
has no jukebox runtime dependencies). The suite runs in well under a second,
so it belongs in every pre-push check; the same tests run in the
`pythonpackage_future3.yml` CI workflow. Manual testing on the Pi is then only
needed for what genuinely cannot be simulated: audio output, the real
librespot binary, and Spotify's server-side behaviour.

## Known Limitations & Future Work

- **Token expiry** — spotipy handles refresh automatically as long as a refresh token
  exists. If the refresh token ever expires (rare), the user must re-authorise via the UI.
- **Single device** — the plugin targets one device at a time. Switching devices mid-session
  requires going to Settings.
- **No cover art for Spotify** — the player screen shows the placeholder icon; the
  album art URL from the Web API is not yet wired into the cover cache.
- **raspotify recommended** — without raspotify, Spotify must be open on some other device
  for playback to work. With raspotify the Pi itself is the speaker.
