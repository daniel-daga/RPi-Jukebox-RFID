#!/usr/bin/env bash
# Reads SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET from a .env file
# and writes them into shared/settings/jukebox.yaml.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
ENV_FILE="${1:-$PROJECT_ROOT/.env}"
CONFIG="$PROJECT_ROOT/shared/settings/jukebox.yaml"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: jukebox.yaml not found at $CONFIG"
    exit 1
fi

# Parse .env (ignore comments and blank lines)
CLIENT_ID=$(grep -E '^SPOTIFY_CLIENT_ID=' "$ENV_FILE" | sed 's/^SPOTIFY_CLIENT_ID=//;s/[[:space:]]//g;s/"//g')
CLIENT_SECRET=$(grep -E '^SPOTIFY_CLIENT_SECRET=' "$ENV_FILE" | sed 's/^SPOTIFY_CLIENT_SECRET=//;s/[[:space:]]//g;s/"//g')

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "ERROR: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in $ENV_FILE"
    exit 1
fi

# Update the values in jukebox.yaml using sed
sed -i \
    -e "/^playerspotify:/,/^[^ ]/ s|^\(  client_id:\).*|\1 $CLIENT_ID|" \
    -e "/^playerspotify:/,/^[^ ]/ s|^\(  client_secret:\).*|\1 $CLIENT_SECRET|" \
    "$CONFIG"

echo "Injected Spotify credentials into $CONFIG"
echo "  client_id:     ${CLIENT_ID:0:8}..."
echo "  client_secret: ${CLIENT_SECRET:0:8}..."
