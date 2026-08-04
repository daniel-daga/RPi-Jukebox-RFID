"""Tests for the installer's mopidy.conf generation logic.

Covers the sed substitution of Spotify credentials (incl. special
characters) into misc/sampleconfigs/mopidy.conf.sample - previously only
verified by grepping /etc/mopidy/mopidy.conf after a full installation
run inside a Docker/QEMU container.
"""

import configparser
import subprocess

from conftest import SPECIAL_CLIENT_ID, SPECIAL_CLIENT_SECRET, TESTS_DIR


def generate_conf(tmp_path, client_id, client_secret, audio_dir):
    out = tmp_path / "mopidy.conf"
    subprocess.run(
        [
            "bash",
            str(TESTS_DIR / "generate_mopidy_conf.sh"),
            client_id,
            client_secret,
            audio_dir,
            str(out),
        ],
        check=True,
    )
    return out


def parse_conf(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    return parser


def test_simple_credentials_are_substituted(tmp_path):
    conf = generate_conf(tmp_path, "myclientid", "myclientsecret", "/home/pi/audio")
    parsed = parse_conf(conf)
    assert parsed["spotify"]["client_id"] == "myclientid"
    assert parsed["spotify"]["client_secret"] == "myclientsecret"
    assert parsed["local"]["media_dir"] == "/home/pi/audio"


def test_no_placeholders_left(tmp_path):
    conf = generate_conf(tmp_path, "id", "secret", "/audio")
    content = conf.read_text(encoding="utf-8")
    assert "%spotify_client_id%" not in content
    assert "%spotify_client_secret%" not in content
    assert "%DIRaudioFolders%" not in content


def test_special_characters_survive_substitution(tmp_path):
    """The credentials used by run_installation_spotify.sh: quotes,
    backslash, ampersand, pipe, umlauts, currency signs, ..."""
    conf = generate_conf(
        tmp_path,
        SPECIAL_CLIENT_ID,
        SPECIAL_CLIENT_SECRET,
        "/home/pi/RPi-Jukebox-RFID/shared/audiofolders",
    )
    parsed = parse_conf(conf)
    assert parsed["spotify"]["client_id"] == SPECIAL_CLIENT_ID
    assert parsed["spotify"]["client_secret"] == SPECIAL_CLIENT_SECRET


def test_generated_config_sections_are_validated_by_mopidy(mopidy):
    """The test instance boots from the generated config, so a malformed
    section fails the whole run rather than being ignored.

    This only holds for sections whose extension is installed. 'iris' is
    pip-only and 'spotify' is deliberately replaced by the mock backend,
    so Mopidy skips those two - they are not covered here.
    """
    logs = mopidy.logs()
    for section in ("local", "file", "m3u", "mpd", "http"):
        assert f"Ignoring config section '{section}'" not in logs, (
            f"[{section}] was not validated - the extension is missing, so a "
            f"broken [{section}] config would pass unnoticed"
        )


def test_generated_conf_is_wellformed(tmp_path):
    """The whole file must stay parseable after substitution."""
    conf = generate_conf(tmp_path, SPECIAL_CLIENT_ID, SPECIAL_CLIENT_SECRET, "/audio")
    parsed = parse_conf(conf)
    for section in ("local", "file", "m3u", "audio", "mpd", "http", "iris", "spotify"):
        assert parsed.has_section(section), f"section [{section}] lost"
    assert parsed["spotify"]["enabled"] == "true"
