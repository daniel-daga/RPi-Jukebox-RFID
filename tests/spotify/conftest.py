import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import wave

import pytest

from mpd_client import MPDClient

TESTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
PYLIB_DIR = TESTS_DIR / "pylib"

# The same special-character credentials the installation test uses
# (see scripts/installscripts/tests/run_installation_spotify.sh)
SPECIAL_CLIENT_ID = (
    "a!b\"c§d$e%f&g/h(i)j=k?l´m`n²o³p{q[r]s}t\\u+v*w~x#y'zß,ä;ö.ü:Ä-Ö_Ü 1@2€3^4°5|67890"
)
SPECIAL_CLIENT_SECRET = "myclient+SECRET/0123456789="

MOPIDY_STARTUP_TIMEOUT = 90


def find_mopidy_python():
    """Find a python interpreter that has mopidy + mopidy-mpd installed.

    The distro packages (apt install mopidy mopidy-mpd) install into the
    distro python, which is not necessarily the python running pytest.
    Override with MOPIDY_PYTHON=/path/to/python if auto-detection fails.
    """
    candidates = []
    if os.environ.get("MOPIDY_PYTHON"):
        candidates.append(os.environ["MOPIDY_PYTHON"])
    candidates += [
        "/usr/bin/python3",
        sys.executable,
        "python3",
        "python3.13",
        "python3.12",
        "python3.11",
    ]
    seen = set()
    for candidate in candidates:
        path = shutil.which(candidate)
        if not path or path in seen:
            continue
        seen.add(path)
        # mopidy.commands pulls in GStreamer via gi, so this also proves
        # the interpreter matches the installed PyGObject C extension
        probe = subprocess.run(
            [path, "-c", "import mopidy.commands, mopidy_mpd"],
            capture_output=True,
        )
        if probe.returncode == 0:
            return path
    return None


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def write_silence_wav(path, seconds=30):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000 * seconds)


class MopidyServer:
    def __init__(self, proc, port, playlists_dir, audio_folders_dir, log_file):
        self.proc = proc
        self.port = port
        self.playlists_dir = playlists_dir
        self.audio_folders_dir = audio_folders_dir
        self.log_file = log_file

    def logs(self):
        return self.log_file.read_text(errors="replace")


@pytest.fixture(scope="session")
def mopidy(tmp_path_factory):
    """A running Mopidy instance with MPD frontend and mock spotify backend.

    The base config is generated from misc/sampleconfigs/mopidy.conf.sample
    with the installer's substitution logic, so Mopidy also proves that a
    freshly 'installed' config is valid and bootable.
    """
    python = find_mopidy_python()
    if python is None:
        pytest.fail(
            "No python interpreter with mopidy + mopidy-mpd found. "
            "Install with: sudo apt-get install mopidy mopidy-mpd "
            "(or set MOPIDY_PYTHON=/path/to/python)"
        )

    tmp = tmp_path_factory.mktemp("mopidy")
    audio_folders_dir = tmp / "audiofolders"
    playlists_dir = tmp / "playlists"
    audio_folders_dir.mkdir()
    playlists_dir.mkdir()

    media_file = tmp / "silence.wav"
    write_silence_wav(media_file)

    base_conf = tmp / "mopidy.conf"
    subprocess.run(
        [
            "bash",
            str(TESTS_DIR / "generate_mopidy_conf.sh"),
            SPECIAL_CLIENT_ID,
            SPECIAL_CLIENT_SECRET,
            str(audio_folders_dir),
            str(base_conf),
        ],
        check=True,
    )

    port = get_free_port()
    # Overrides for a headless CI environment: no sound card (fakesink),
    # no HTTP frontend, and the extensions that are not installed in CI
    # (spotify, iris, local) are disabled. Mopidy would only warn about
    # their config sections anyway, but disabling keeps the log clean.
    override_conf = tmp / "override.conf"
    override_conf.write_text(
        f"""\
[core]
cache_dir = {tmp}/cache
config_dir = {tmp}/config
data_dir = {tmp}/data

[audio]
# sync=true makes the fake sink consume the stream in real time,
# otherwise tracks "finish" within milliseconds and the player state
# races back to 'stop'
output = fakesink sync=true

[mpd]
enabled = true
hostname = 127.0.0.1
port = {port}

[http]
enabled = false

[file]
enabled = false

[spotify]
enabled = false

[iris]
enabled = false

[local]
enabled = false

[m3u]
enabled = true
playlists_dir = {playlists_dir}
default_encoding = UTF-8
default_extension = .m3u

[mockspotify]
enabled = true
media_file = {media_file}
""",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYLIB_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    log_file = tmp / "mopidy.log"
    with open(log_file, "wb") as log:
        proc = subprocess.Popen(
            [python, "-m", "mopidy", "--config", f"{base_conf}:{override_conf}"],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )

    server = MopidyServer(proc, port, playlists_dir, audio_folders_dir, log_file)

    deadline = time.monotonic() + MOPIDY_STARTUP_TIMEOUT
    while True:
        if proc.poll() is not None:
            pytest.fail(
                f"Mopidy exited with code {proc.returncode} during startup:\n"
                + server.logs()
            )
        try:
            MPDClient(port=port).close()
            break
        except OSError:
            if time.monotonic() > deadline:
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail(
                    "Mopidy MPD frontend did not come up in time:\n" + server.logs()
                )
            time.sleep(0.5)

    yield server

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture()
def mpd(mopidy):
    """A fresh MPD protocol connection with a clean tracklist."""
    client = MPDClient(port=mopidy.port)
    client.command("clear")
    yield client
    try:
        client.command("stop")
        client.command("clear")
    except OSError:
        pass
    client.close()


def wait_until(condition, description, timeout=20):
    """Poll until condition() is truthy.

    Mopidy acknowledges playback commands before the audio pipeline has
    actually changed state, so anything asserting on player state has to
    poll instead of checking once.
    """
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = condition()
        if last:
            return last
        time.sleep(0.2)
    raise AssertionError(
        f"Timed out after {timeout}s waiting for {description} (last value: {last!r})"
    )


def wait_for_state(client, state, timeout=20):
    wait_until(
        lambda: client.status().get("state") == state,
        f"player state '{state}'",
        timeout=timeout,
    )
