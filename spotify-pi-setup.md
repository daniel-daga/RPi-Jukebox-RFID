# Spotify on the Pi — Setup Checklist

## 1. Spotify Developer App

In your [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), add a Redirect URI:

```
http://<pi-ip>:8888/callback
```

e.g. `http://192.168.1.42:8888/callback`. Keep the existing ones, just add this one. Click **Save**.

---

## 2. Run the setup script on the Pi

```bash
cd /home/pi/RPi-Jukebox-RFID
bash src/jukebox/components/playerspotify/setup.inc.sh
```

This single script installs spotipy, enables the `playerspotify` module in
`shared/settings/jukebox.yaml`, and sets up librespot as a user service with
the PulseAudio backend — the Pi itself becomes the Spotify playback device
(Connect device name **Phoniebox**) and its audio follows the Jukebox output
switching, including a Bluetooth speaker as secondary output.

Set `SKIP_LIBRESPOT=1` if you only want remote control of other devices.
Then restart the jukebox service.

---

## 3. Authenticate via the Web UI

1. Open the Jukebox web UI in your browser → **Settings → Spotify**
2. Enter Client ID, Client Secret, and set Redirect URI to `http://<pi-ip>:8888/callback`
3. Click **Save**
4. Click **Connect with Spotify** — a browser tab opens
5. Approve access — the tab shows "Spotify connected!"
6. The Connect section should now show a green checkmark and your username

That's it for the playback device: the Jukebox now logs the librespot device
into your Spotify account automatically (no phone needed) and targets it by
name (config key `playerspotify.device_name`). To play elsewhere instead,
pick an explicit device in **Settings → Spotify → Device** — an explicit
choice overrides the name lookup.

Full guide including Bluetooth speaker routing:
[Spotify on a Bluetooth Speaker](documentation/builders/spotify-bluetooth.md).

---

## 4. Test an RFID Card

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
| "No active device" / device not found | Check `systemctl --user status librespot.service`; restart the jukebox so the automatic librespot login runs again (watch the log for `librespot auto-login`) |
| Log says token lacks the 'streaming' permission | Settings → Spotify → Disconnect, then Connect again, then restart the jukebox |
| Plugin not loading | Check `playerspotify` is under `modules.named` in jukebox.yaml and spotipy is installed |
| Token expired | Settings → Spotify → Disconnect, then Connect again |
