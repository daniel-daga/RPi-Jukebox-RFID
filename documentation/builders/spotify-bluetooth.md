# Spotify on a Bluetooth Speaker

This guide covers the full chain: **tap an RFID card → the Jukebox starts a
Spotify song → the audio plays on a Bluetooth speaker connected to the Pi.**

How the pieces fit together:

```text
RFID card ──> spotify.ctrl.play_card ──> Spotify Web API
                                              │  (starts playback on the
                                              ▼   'Phoniebox' Connect device)
                                    librespot on the Pi
                                              │  (PulseAudio backend)
                                              ▼
                     PulseAudio ──> secondary output = Bluetooth speaker
```

The Spotify plugin controls playback through the Spotify Web API. The sound
itself is produced by **librespot**, a Spotify Connect client running on the
Pi. Because librespot plays through **PulseAudio**, its audio follows the
Jukebox's normal output switching — including the Bluetooth speaker configured
as the secondary output.

Requirements: **Spotify Premium** account, a Bluetooth speaker, and a working
Jukebox installation.

## Step 1: Run the Spotify setup script

```bash
cd ~/RPi-Jukebox-RFID
bash src/jukebox/components/playerspotify/setup.inc.sh
```

This installs the Python dependency, enables the `playerspotify` module in
`jukebox.yaml`, and sets up librespot (step 3) in one go.

Then create a Spotify Developer App and connect your account via the web UI
(**Settings → Spotify**) as described in
[the Spotify setup checklist](../../spotify-pi-setup.md).

## Step 2: Pair the Bluetooth speaker

Pair, trust, and connect the speaker as described in
[Audio → Bluetooth](audio.md#bluetooth):

```bash
$ bluetoothctl
[bluetooth]# scan on
[bluetooth]# pair <MAC>
[bluetooth]# trust <MAC>
[bluetooth]# connect <MAC>
```

Then re-run the [audio configuration tool](../developers/coreapps.md#Audio) so
the speaker is registered as the Jukebox's **secondary audio output**. With the
default `toggle_on_connect: true`, the Jukebox switches to the speaker
automatically whenever it connects; you can also switch manually via the web
UI or bind `volume.ctrl.toggle_output` to a card.

## Step 3: librespot (makes the Pi a Spotify device)

Already done if you ran the setup script in step 1. To run it separately:

```bash
bash src/jukebox/components/playerspotify/setup_librespot.inc.sh
```

This installs the librespot binary (via the raspotify package) and runs it as
a systemd **user** service with the **PulseAudio backend**. The Pi then
appears as a Spotify Connect device named **Phoniebox**.

> [!IMPORTANT]
> Do not use the stock raspotify system service for this. It runs as its own
> system user and outputs to ALSA directly, which bypasses PulseAudio — the
> audio would ignore the Jukebox's output switching and never reach the
> Bluetooth speaker. The setup script disables it and installs the user
> service instead.

To use a different device name, pass `LIBRESPOT_NAME="My Box"` to the script
and set the same name in `jukebox.yaml`:

```yaml
playerspotify:
  device_name: My Box
```

**Account activation happens automatically** — no phone needed: as soon as
the Jukebox is connected to Spotify (step 1), it logs the librespot device
into your account with its own OAuth token and librespot keeps reusable
credentials from then on. If you connected Spotify *before* installing
librespot, just restart the jukebox service once.

> [!NOTE]
> The automatic login needs librespot v0.5+ and a token with the 'streaming'
> permission. If the log reports the permission is missing, disconnect and
> re-connect Spotify once in the web UI. As a fallback, the manual activation
> still works: select **Phoniebox** in the device picker of any Spotify app
> (phone or desktop) on the same network.

## Step 4: Map a card

Add a card to `shared/settings/cards.yaml`:

```yaml
'<your-card-id>':
  package: spotify
  plugin: ctrl
  method: play_card
  args: ['spotify:track:4uLU6hMCjMI75M1A2tKUQC']
```

Track, album, and playlist URIs all work (get them via *Share → Copy link* in
Spotify; `https://open.spotify.com/track/<id>` corresponds to
`spotify:track:<id>`).

The plugin looks up the playback device by `device_name` automatically —
you do not need to select a device ID in the web UI. An explicit choice under
**Settings → Spotify → Device** takes precedence if you ever want to play on
a different device (leave it on *Active device* for the Pi/Bluetooth setup).

## Step 5: Tap the card

Tap the card: the song starts on the Pi and comes out of whichever output is
active — the Bluetooth speaker when it is connected, otherwise the primary
output. A second tap of the same card toggles pause/play (configurable via
`second_swipe_action`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Card starts playback on your phone instead of the Pi | librespot is not running or its name doesn't match `device_name`. Check `systemctl --user status librespot.service` |
| "No Connect device named 'Phoniebox' found" in the logs | Restart the jukebox service so the automatic librespot login runs again; check the log for `librespot auto-login` messages. Fallback: select the device once in any Spotify app |
| Log says the token lacks the 'streaming' permission | Disconnect and re-connect Spotify in the web UI (Settings → Spotify), then restart the jukebox |
| Audio comes from the Pi's jack instead of the Bluetooth speaker | Speaker not connected, or not configured as secondary output — re-run the audio config tool and check `pactl list sinks short` shows a `bluez_sink...` |
| Sound stops when you log out of SSH | Run `sudo loginctl enable-linger $(whoami)` (the setup script does this) |
| Playback fails right after a reboot | librespot may take a few seconds to register with Spotify; also make sure the Bluetooth speaker is switched on so it can auto-connect |
