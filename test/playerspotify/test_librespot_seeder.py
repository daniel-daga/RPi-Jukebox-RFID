import importlib.util
import pathlib
import subprocess

# Load the module directly from its file: importing the playerspotify package
# would pull in daemon dependencies (spotipy, zmq) not present in the test env
_module_path = (pathlib.Path(__file__).resolve().parents[2]
                / 'src' / 'jukebox' / 'components' / 'playerspotify' / 'librespot_seeder.py')
_spec = importlib.util.spec_from_file_location('librespot_seeder', _module_path)
librespot_seeder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(librespot_seeder)


class FakeProc:
    """Stand-in for subprocess.Popen result"""

    def __init__(self, returncode=None):
        # returncode None = still running
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True


def test_credentials_path_expands_home(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    path = librespot_seeder.credentials_path('~/.cache/librespot')
    assert path == str(tmp_path / '.cache' / 'librespot' / 'credentials.json')


def test_has_cached_credentials(tmp_path):
    cache = tmp_path / 'cache'
    assert not librespot_seeder.has_cached_credentials(str(cache))
    cache.mkdir()
    (cache / 'credentials.json').write_text('{}')
    assert librespot_seeder.has_cached_credentials(str(cache))


def test_build_seed_command():
    cmd = librespot_seeder.build_seed_command('/usr/bin/librespot', 'tok123',
                                              '/tmp/cache', 'Phoniebox')
    assert cmd[0] == '/usr/bin/librespot'
    assert cmd[cmd.index('--name') + 1] == 'Phoniebox'
    assert cmd[cmd.index('--access-token') + 1] == 'tok123'
    assert cmd[cmd.index('--cache') + 1] == '/tmp/cache'
    # The seed run must not clash with the running librespot service
    assert '--disable-discovery' in cmd
    assert cmd[cmd.index('--backend') + 1] == 'pipe'


def test_supports_access_token():
    def fake_run_yes(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='... --access-token <token> ...', stderr='')

    def fake_run_no(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='old librespot 0.4', stderr='')

    def fake_run_raises(cmd, **kwargs):
        raise OSError('no such binary')

    assert librespot_seeder.supports_access_token('librespot', run=fake_run_yes) is True
    assert librespot_seeder.supports_access_token('librespot', run=fake_run_no) is False
    assert librespot_seeder.supports_access_token('librespot', run=fake_run_raises) is False


def test_seed_success_when_credentials_appear(tmp_path):
    cache = tmp_path / 'cache'
    procs = []

    def fake_popen(cmd, **kwargs):
        # librespot 'logs in' immediately: credentials file appears
        (cache / 'credentials.json').write_text('{}')
        proc = FakeProc(returncode=None)
        procs.append(proc)
        return proc

    ok = librespot_seeder.seed('librespot', 'tok', str(cache), 'Phoniebox',
                               timeout=2, poll_interval=0.01, popen=fake_popen)
    assert ok is True
    # The still-running seed process must be cleaned up
    assert procs[0].terminated is True


def test_seed_failure_when_process_exits_without_credentials(tmp_path):
    cache = tmp_path / 'cache'

    def fake_popen(cmd, **kwargs):
        # librespot exits right away (e.g. invalid token), no credentials
        return FakeProc(returncode=1)

    ok = librespot_seeder.seed('librespot', 'tok', str(cache), 'Phoniebox',
                               timeout=2, poll_interval=0.01, popen=fake_popen)
    assert ok is False


def test_seed_timeout_without_credentials(tmp_path):
    cache = tmp_path / 'cache'
    procs = []

    def fake_popen(cmd, **kwargs):
        proc = FakeProc(returncode=None)
        procs.append(proc)
        return proc

    ok = librespot_seeder.seed('librespot', 'tok', str(cache), 'Phoniebox',
                               timeout=0.05, poll_interval=0.01, popen=fake_popen)
    assert ok is False
    assert procs[0].terminated is True
