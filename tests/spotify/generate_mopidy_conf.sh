#!/usr/bin/env bash

# Generate a mopidy.conf from the shipped sample config the same way
# the installer does, so the substitution logic (incl. escaping of
# special characters in Spotify credentials) is testable without
# running the full installation.
#
# Keep the sed calls below in sync with existing_assets() in
# scripts/installscripts/install-jukebox.sh ("Spotify config" block).
#
# Usage:
#   generate_mopidy_conf.sh <client_id> <client_secret> <audio_folders_dir> <output_file>

set -e

SPOTIclientid="$1"
SPOTIclientsecret="$2"
DIRaudioFolders="$3"
mopidy_conf="$4"

if [ -z "${mopidy_conf}" ]; then
    echo "Usage: $0 <client_id> <client_secret> <audio_folders_dir> <output_file>" >&2
    exit 1
fi

# The absolute path to the folder which contains this script
PATHDATA="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
jukebox_dir="${PATHDATA}/../.."

# escape_for_sed() - same helper the installer uses
source "${jukebox_dir}"/scripts/helperscripts/inc.helper.sh

cp "${jukebox_dir}"/misc/sampleconfigs/mopidy.conf.sample "${mopidy_conf}"
# Change vars to match install config
sed -i 's|%spotify_client_id%|'"$(escape_for_sed "$SPOTIclientid")"'|' "${mopidy_conf}"
sed -i 's|%spotify_client_secret%|'"$(escape_for_sed "$SPOTIclientsecret")"'|' "${mopidy_conf}"
# for $DIRaudioFolders using | as alternate regex delimiter because of the folder path slash
sed -i 's|%DIRaudioFolders%|'"$(escape_for_sed "$DIRaudioFolders")"'|' "${mopidy_conf}"
