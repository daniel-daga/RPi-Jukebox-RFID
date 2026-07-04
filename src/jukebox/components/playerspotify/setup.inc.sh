#!/usr/bin/env bash
# One-shot setup for Spotify playback on the jukebox. Does everything that
# can be automated:
#   1. Installs the Python dependency (spotipy)
#   2. Enables the 'playerspotify' module in shared/settings/jukebox.yaml
#   3. Installs librespot as a user service with the PulseAudio backend,
#      so the Pi itself is the playback device and the audio follows the
#      jukebox output switching (e.g. Bluetooth speaker)
#      (skip with SKIP_LIBRESPOT=1)
#
# What remains manual: entering the Spotify app credentials in the web UI
# (Settings → Spotify) and clicking 'Connect with Spotify' once. Everything
# else — including logging the librespot device into your account — happens
# automatically after that.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../../../.."

echo "Setting up Spotify player plugin..."

# Use the project venv if present, otherwise fall back to system pip
VENV="$PROJECT_ROOT/.venv"
if [ -f "$VENV/bin/pip" ]; then
    PIP="$VENV/bin/pip"
    PYTHON="$VENV/bin/python"
else
    PIP="pip3"
    PYTHON="python3"
fi

# 1. Install the Python dependency
"$PIP" install -r "$SCRIPT_DIR/requirements.txt"

# 2. Enable the module in the jukebox configuration (if it exists already)
CONFIG_FILE="$PROJECT_ROOT/shared/settings/jukebox.yaml"
if [ -f "$CONFIG_FILE" ]; then
    "$PYTHON" - "$CONFIG_FILE" << 'EOF' || echo "Could not update the config automatically - add 'spotify: playerspotify' under modules.named in jukebox.yaml yourself."
import sys
from ruamel.yaml import YAML

yaml = YAML()
path = sys.argv[1]
with open(path) as f:
    config = yaml.load(f)
named = config.setdefault('modules', {}).setdefault('named', {})
if named.get('spotify') == 'playerspotify':
    print(f"Module 'playerspotify' already enabled in {path}")
else:
    named['spotify'] = 'playerspotify'
    with open(path, 'w') as f:
        yaml.dump(config, f)
    print(f"Enabled module 'spotify: playerspotify' in {path}")
EOF
else
    echo "No jukebox.yaml found at $CONFIG_FILE (first start pending?)."
    echo "Add 'spotify: playerspotify' under modules.named once it exists."
fi

# 3. Set up librespot so the Pi itself plays the audio
if [ "${SKIP_LIBRESPOT:-0}" != "1" ]; then
    bash "$SCRIPT_DIR/setup_librespot.inc.sh"
fi

echo ""
echo "Done! Remaining steps (one-time, all in the browser):"
echo "  1. Create a Spotify Developer App at https://developer.spotify.com/dashboard"
echo "     and add this Redirect URI to it:"
echo "       http://<your-pi-hostname-or-ip>:8888/callback"
echo "  2. Restart the jukebox service"
echo "  3. Open the web UI → Settings → Spotify: enter the app credentials"
echo "     and click 'Connect with Spotify'"
echo ""
echo "The jukebox then logs the librespot device into your Spotify account"
echo "automatically - no phone needed. Map a card and tap it."
echo "Full guide: documentation/builders/spotify-bluetooth.md"
