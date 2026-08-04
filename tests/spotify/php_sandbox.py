"""Helper to run scripts/playlist_recursive_by_folder.php in a sandbox.

The script resolves the audio folders and edition relative to its own
location, so it is copied (with its dependencies) into a temporary
Phoniebox-like directory tree instead of touching the repo checkout.
"""

import pathlib
import shutil
import subprocess

TESTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]


class PhpSandbox:
    def __init__(self, root, audio_folders_dir):
        self.root = root
        self.audio_folders_dir = audio_folders_dir

    def set_edition(self, edition):
        (self.root / "settings" / "edition").write_text(edition + "\n")

    def add_spotify_folder(self, name, uri):
        folder = self.audio_folders_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        # like a real spotify.txt written over samba/web UI: trailing newline
        (folder / "spotify.txt").write_text(uri + "\n")
        return folder

    def add_local_folder(self, name, filenames):
        folder = self.audio_folders_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            (folder / filename).touch()
        return folder

    def playlist(self, folder, recursive=False):
        """Run the real PHP playlist generator, return non-empty lines."""
        cmd = [
            "php",
            str(self.root / "scripts" / "playlist_recursive_by_folder.php"),
            "--folder",
            folder,
        ]
        if recursive:
            cmd += ["--list", "recursive"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line for line in result.stdout.splitlines() if line.strip()]


def make_php_sandbox(tmp_path, edition="plusSpotify", audio_folders_dir=None):
    root = tmp_path / "phoniebox"
    (root / "scripts").mkdir(parents=True)
    (root / "htdocs").mkdir()
    (root / "settings").mkdir()
    shutil.copy(
        REPO_ROOT / "scripts" / "playlist_recursive_by_folder.php",
        root / "scripts",
    )
    shutil.copy(REPO_ROOT / "htdocs" / "func.php", root / "htdocs")

    if audio_folders_dir is None:
        audio_folders_dir = root / "shared" / "audiofolders"
        audio_folders_dir.mkdir(parents=True)
    (root / "settings" / "Audio_Folders_Path").write_text(str(audio_folders_dir))
    (root / "settings" / "version").write_text("2.8.0\n")

    sandbox = PhpSandbox(root, pathlib.Path(audio_folders_dir))
    sandbox.set_edition(edition)
    return sandbox
