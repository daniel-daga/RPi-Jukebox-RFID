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
        # like a real spotify.txt written over samba/web UI: trailing newline
        return self.write_uri_file(name, "spotify.txt", uri + "\n")

    def write_uri_file(self, name, filename, content):
        """Create a folder holding a URI file (spotify.txt, livestream.txt,
        podcast.txt) with exact content, including line endings."""
        folder = self.audio_folders_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(content, newline="")
        return folder

    def add_local_folder(self, name, filenames):
        folder = self.audio_folders_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            (folder / filename).touch()
        return folder

    def playlist_raw(self, folder, recursive=False):
        """Run the real PHP playlist generator, return its exact output.

        Prefer this over playlist(): the m3u is written to disk verbatim,
        so blank lines and stray whitespace are part of the behaviour and
        assertions should be able to see them.
        """
        cmd = [
            "php",
            str(self.root / "scripts" / "playlist_recursive_by_folder.php"),
            "--folder",
            folder,
        ]
        if recursive:
            cmd += ["--list", "recursive"]
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

    def playlist(self, folder, recursive=False):
        """Entries only, with blank lines dropped.

        Convenience for assertions about *which* entries are generated;
        it deliberately normalises away whitespace artifacts, so use
        playlist_raw() when the exact file content matters.
        """
        return [
            line
            for line in self.playlist_raw(folder, recursive).splitlines()
            if line.strip()
        ]


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
