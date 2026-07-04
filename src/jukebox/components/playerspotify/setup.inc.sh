#!/usr/bin/env bash
# Setup script for the Spotify player plugin
# Run this once on the Raspberry Pi before enabling the plugin.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../../../.."

echo "Setting up Spotify player plugin..."

# Use the project venv if present, otherwise fall back to system pip
VENV="$PROJECT_ROOT/.venv"
if [ -f "$VENV/bin/pip" ]; then
    PIP="$VENV/bin/pip"
else
    PIP="pip3"
fi

# Install the Python dependency
"$PIP" install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Done! Next steps:"
echo "  1. Create a Spotify Developer App at https://developer.spotify.com/dashboard"
echo "     and add this Redirect URI to it:"
echo "       http://<your-pi-hostname-or-ip>:8888/callback"
echo "  2. Add your credentials to jukebox.yaml under 'playerspotify'"
echo "  3. Add 'spotify: playerspotify' under modules.named in jukebox.yaml"
echo "  4. Restart the jukebox, then open Settings → Spotify → Connect with Spotify"
echo ""
echo "  For audio playback on the Pi itself (e.g. through a Bluetooth speaker),"
echo "  also set up librespot with the PulseAudio backend:"
echo "    bash $SCRIPT_DIR/setup_librespot.inc.sh"
echo "  See documentation/builders/spotify-bluetooth.md for the full guide."
echo ""
