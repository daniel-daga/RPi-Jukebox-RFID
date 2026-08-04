"""Build a runnable Phoniebox tree so the real shell scripts can be executed.

rfid_trigger_play.sh and playout_controls.sh resolve everything relative
to their own location, so the scripts (plus the settings/ and htdocs/
they read) are copied into a temporary tree. The audio folders and
playlists directories are pointed at the running Mopidy instance, so the
scripts drive the same player the tests inspect.

Note the scripts talk to 'localhost 6600' hardcoded (resume_play.sh,
rfid_trigger_play.sh), so they only work when the test Mopidy owns the
standard MPD port - see pick_mpd_port() in conftest.
"""

import pathlib
import shutil
import subprocess

TESTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]


class PhonieboxSandbox:
    def __init__(self, root, audio_folders_dir, playlists_dir):
        self.root = root
        self.scripts = root / "scripts"
        self.audio_folders_dir = audio_folders_dir
        self.playlists_dir = playlists_dir

    def run(self, script, *args, timeout=120):
        """Run one of the real Phoniebox scripts."""
        return subprocess.run(
            ["bash", str(self.scripts / script), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def trigger_play(self, *args):
        return self.run("rfid_trigger_play.sh", *args)

    def add_spotify_folder(self, name, uri):
        folder = self.audio_folders_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "spotify.txt").write_text(uri + "\n")
        return folder

    def add_shortcut(self, card_id, folder):
        (self.root / "shared" / "shortcuts" / card_id).write_text(folder + "\n")

    def playlist_file(self, name):
        return self.playlists_dir / f"{name}.m3u"


def make_phoniebox_sandbox(tmp_path, audio_folders_dir, playlists_dir,
                           edition="plusSpotify"):
    root = tmp_path / "phoniebox"
    root.mkdir()
    for item in ("scripts", "htdocs", "settings"):
        shutil.copytree(REPO_ROOT / item, root / item)
    for item in ("logs", "shared/shortcuts"):
        (root / item).mkdir(parents=True, exist_ok=True)

    settings = root / "settings"
    shutil.copy(settings / "debugLogging.conf.sample", settings / "debugLogging.conf")
    # pre-create so the script does not try to chown it to pi:www-data
    shutil.copy(
        settings / "rfid_trigger_play.conf.sample", settings / "rfid_trigger_play.conf"
    )
    (settings / "Audio_Folders_Path").write_text(str(audio_folders_dir))
    (settings / "Playlists_Folders_Path").write_text(str(playlists_dir))
    (settings / "edition").write_text(edition + "\n")
    (settings / "version").write_text("2.8.0\n")
    (settings / "Latest_Folder_Played").write_text("")
    (settings / "Latest_Playlist_Played").write_text("")

    # Build settings/global.conf the way a running box does. It has to be
    # sourced from within scripts/ because rfid_trigger_play.sh refers to
    # 'inc.writeGlobalConfig.sh' without a path and would otherwise only
    # find it when the caller's working directory happens to be scripts/.
    subprocess.run(
        ["bash", "-c", ". ./inc.writeGlobalConfig.sh"],
        cwd=root / "scripts",
        capture_output=True,
        text=True,
        timeout=120,
    )

    return PhonieboxSandbox(root, pathlib.Path(audio_folders_dir),
                            pathlib.Path(playlists_dir))
