#!/usr/bin/env bash
# Setup script for the Spotify player plugin
# Run this once on the Raspberry Pi before enabling the plugin.

echo "Setting up Spotify player plugin..."

# Install the Python dependency
pip3 install -r "$(dirname "$0")/requirements.txt"

echo ""
echo "Done! Next steps:"
echo "  1. Create a Spotify Developer App at https://developer.spotify.com/dashboard"
echo "     and add this Redirect URI to it:"
echo "       http://<your-pi-hostname-or-ip>:8888/callback"
echo "  2. Add your credentials to jukebox.yaml under 'playerspotify'"
echo "  3. Add 'spotify: playerspotify' under modules.named in jukebox.yaml"
echo "  4. Restart the jukebox, then open Settings → Spotify → Connect with Spotify"
echo ""
echo "  For audio playback on the Pi itself, also install raspotify:"
echo "    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh"
echo ""
