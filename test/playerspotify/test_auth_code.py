import importlib.util
import pathlib

# Load the module directly from its file: importing the playerspotify package
# would pull in daemon dependencies (spotipy, zmq) not present in the test env
_module_path = (pathlib.Path(__file__).resolve().parents[2]
                / 'src' / 'jukebox' / 'components' / 'playerspotify' / 'auth_code.py')
_spec = importlib.util.spec_from_file_location('auth_code', _module_path)
auth_code = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auth_code)

extract_auth_code = auth_code.extract_auth_code


def test_full_redirect_url():
    url = 'http://127.0.0.1:8888/callback?code=AQDxyz123&state=abc'
    assert extract_auth_code(url) == 'AQDxyz123'


def test_https_redirect_url():
    url = 'https://example.com/callback?code=AQDxyz123'
    assert extract_auth_code(url) == 'AQDxyz123'


def test_query_string_only():
    assert extract_auth_code('?code=AQDxyz123&state=abc') == 'AQDxyz123'
    assert extract_auth_code('code=AQDxyz123') == 'AQDxyz123'


def test_bare_code():
    assert extract_auth_code('AQDxyz123') == 'AQDxyz123'


def test_surrounding_whitespace_is_stripped():
    assert extract_auth_code('  AQDxyz123\n') == 'AQDxyz123'
    assert extract_auth_code(' http://127.0.0.1:8888/callback?code=AQDxyz123 ') == 'AQDxyz123'


def test_url_without_code_returns_none():
    assert extract_auth_code('http://127.0.0.1:8888/callback?error=access_denied') is None
    assert extract_auth_code('http://127.0.0.1:8888/callback') is None


def test_empty_input_returns_none():
    assert extract_auth_code('') is None
    assert extract_auth_code('   ') is None
    assert extract_auth_code(None) is None


def test_empty_code_param_returns_none():
    assert extract_auth_code('http://127.0.0.1:8888/callback?code=&state=x') is None
