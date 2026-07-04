#!/usr/bin/env bash
# Sets up librespot (an open-source Spotify Connect client) on the Pi, so the
# Jukebox itself shows up as a Spotify playback device and the audio comes out
# of the Pi — including a Bluetooth speaker configured as the Jukebox's
# secondary audio output.
#
# Key point: librespot must use the *PulseAudio* backend and run in the same
# user session as PulseAudio and the Jukebox. Only then does Spotify audio
# follow the Jukebox's primary/secondary output switching (e.g. toggling to a
# Bluetooth speaker). The raspotify system service does NOT provide this: it
# runs as its own system user and plays via ALSA directly, bypassing the
# Jukebox audio routing — which is why it gets disabled below.
#
# Usage:
#   bash setup_librespot.inc.sh
# The Spotify Connect device name defaults to 'Phoniebox'; override with:
#   LIBRESPOT_NAME="My Jukebox" bash setup_librespot.inc.sh
# (it must match 'device_name' under 'playerspotify' in jukebox.yaml)

set -e

DEVICE_NAME="${LIBRESPOT_NAME:-Phoniebox}"
# Must match 'playerspotify.librespot.cache_dir' in jukebox.yaml: the jukebox
# logs librespot into the Spotify account by seeding credentials in there
CACHE_DIR="${LIBRESPOT_CACHE:-$HOME/.cache/librespot}"

echo "Setting up librespot (Spotify Connect device name: '${DEVICE_NAME}')..."

# 1. Get the librespot binary. The raspotify package is the easiest way to
#    obtain an up-to-date, Pi-compatible build.
if ! command -v librespot > /dev/null 2>&1; then
    echo "Installing raspotify (provides the librespot binary)..."
    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
fi
LIBRESPOT_BIN="$(command -v librespot || echo /usr/bin/librespot)"

# 2. Disable the raspotify system service (see header for why)
if systemctl list-unit-files raspotify.service > /dev/null 2>&1; then
    echo "Disabling the raspotify system service (replaced by a user service)..."
    sudo systemctl disable --now raspotify.service 2> /dev/null || true
fi

# 3. Run librespot as a systemd *user* service instead
mkdir -p "${CACHE_DIR}"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/librespot.service << EOF
[Unit]
Description=Librespot (Spotify Connect client) for the Jukebox
After=network-online.target sound.target

[Service]
# --backend pulseaudio: audio follows the Jukebox's output switching (Bluetooth!)
# --volume-ctrl fixed --initial-volume 100: the Jukebox controls the volume via
#   PulseAudio; don't let Spotify clients scale it a second time
# --cache: the jukebox seeds login credentials in here (librespot auto-login)
ExecStart=${LIBRESPOT_BIN} --name "${DEVICE_NAME}" --backend pulseaudio --bitrate 160 --initial-volume 100 --volume-ctrl fixed --cache "${CACHE_DIR}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now librespot.service

# Keep the user session (and with it librespot + PulseAudio) running without login
sudo loginctl enable-linger "$(whoami)" 2> /dev/null || true

echo ""
echo "Done! librespot is running as Spotify Connect device '${DEVICE_NAME}'."
echo ""
echo "No phone needed: once you click 'Connect with Spotify' in the web UI"
echo "(Settings → Spotify), the jukebox logs this device into your Spotify"
echo "account automatically. If you were already connected before this setup,"
echo "just restart the jukebox service (or disconnect and re-connect once to"
echo "grant the 'streaming' permission if the log asks for it)."
echo ""
echo "Check the service with:  systemctl --user status librespot.service"
