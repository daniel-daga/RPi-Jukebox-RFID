# Spotify on the Pi — Setup Checklist

## 1. Spotify Developer App

In your [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), add a Redirect URI:

```
http://<pi-ip>:8888/callback
```

e.g. `http://192.168.1.42:8888/callback`. Keep the existing ones, just add this one. Click **Save**.

---

## 2. Install spotipy on the Pi

```bash
cd /home/pi/RPi-Jukebox-RFID
bash src/jukebox/components/playerspotify/setup.inc.sh
```

Or manually:

```bash
pip install spotipy
```

---

## 3. Enable the module in jukebox.yaml

In `shared/settings/jukebox.yaml`, add under `modules.named`:

```yaml
modules:
  named:
    spotify: playerspotify
```

Also add credentials (or do it via the web UI in step 4):

```yaml
playerspotify:
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  redirect_uri: "http://<pi-ip>:8888/callback"
```

---

## 4. Authenticate via the Web UI

1. Open the Jukebox web UI in your browser → **Settings → Spotify**
2. Enter Client ID, Client Secret, and set Redirect URI to `http://<pi-ip>:8888/callback`
3. Click **Save**
4. Click **Connect with Spotify** — a browser tab opens
5. Approve access — the tab shows "Spotify connected!"
6. The Connect section should now show a green checkmark and your username

---

## 5. Playback Device

To have the audio come out of the Pi itself (headphone jack, HiFiBerry, or a
Bluetooth speaker), install librespot with the PulseAudio backend:

```bash
bash src/jukebox/components/playerspotify/setup_librespot.inc.sh
```

The Pi then shows up as Spotify Connect device **Phoniebox** and is targeted
automatically (config key `playerspotify.device_name`). Full guide including
Bluetooth speaker routing: [Spotify on a Bluetooth Speaker](documentation/builders/spotify-bluetooth.md).

Alternatively pick an explicit device in **Settings → Spotify → Device**
(e.g. your phone for testing) — an explicit choice overrides the name lookup.

---

## 6. Test an RFID Card

In `shared/settings/cards.yaml`, add an entry:

```yaml
'<your-card-id>':
  package: spotify
  plugin: ctrl
  method: play_card
  args: ['spotify:playlist:37i9dQZF1DXcBWIGoYBM5M']
```

Swipe the card — music should start. Swipe again — toggles pause/play (default second-swipe action).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "redirect_uri: Not matching configuration" | URI in Spotify dashboard doesn't match `redirect_uri` in jukebox.yaml exactly |
| "No active device" | Open Spotify on the target device first, or set a device ID in Settings → Spotify → Device |
| Plugin not loading | Check `playerspotify` is under `modules.named` in jukebox.yaml and spotipy is installed |
| Token expired | Settings → Spotify → Disconnect, then Connect again |
