#!/usr/bin/env bash

# Run the Spotify feature tests on any Linux machine - no Raspberry Pi,
# no Spotify credentials and no Docker/QEMU required.
#
# Requirements (Debian/Ubuntu):
#   sudo apt-get install mopidy mopidy-mpd mpc gstreamer1.0-plugins-good php-cli
#   python3 -m pip install pytest
#
# Optional:
#   MOPIDY_PYTHON=/path/to/python  python interpreter that has the mopidy
#                                  packages installed (auto-detected otherwise)

set -e

PATHDATA="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if ! python3 -m pytest --version > /dev/null 2>&1; then
    echo "ERROR: pytest is not installed (python3 -m pip install pytest)" >&2
    exit 1
fi

exec python3 -m pytest "${PATHDATA}" -v "$@"
