import importlib.util
import pathlib

# Load the module directly from its file: importing the playerspotify package
# would pull in daemon dependencies (spotipy, zmq) not present in the test env
_module_path = (pathlib.Path(__file__).resolve().parents[2]
                / 'src' / 'jukebox' / 'components' / 'playerspotify' / 'device_resolver.py')
_spec = importlib.util.spec_from_file_location('device_resolver', _module_path)
device_resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(device_resolver)

resolve_device_id = device_resolver.resolve_device_id


DEVICES = [
    {'id': 'aaa111', 'name': 'Phoniebox', 'type': 'Speaker'},
    {'id': 'bbb222', 'name': 'Living Room TV', 'type': 'TV'},
    {'id': 'ccc333', 'name': 'My Phone', 'type': 'Smartphone'},
]


def test_exact_match():
    assert resolve_device_id(DEVICES, 'Phoniebox') == 'aaa111'


def test_match_is_case_insensitive():
    assert resolve_device_id(DEVICES, 'phoniebox') == 'aaa111'
    assert resolve_device_id(DEVICES, 'PHONIEBOX') == 'aaa111'


def test_match_ignores_surrounding_whitespace():
    assert resolve_device_id(DEVICES, '  Phoniebox ') == 'aaa111'
    devices = [{'id': 'x', 'name': ' Phoniebox  '}]
    assert resolve_device_id(devices, 'Phoniebox') == 'x'


def test_no_match_returns_none():
    assert resolve_device_id(DEVICES, 'Kitchen') is None


def test_empty_or_none_name_returns_none():
    assert resolve_device_id(DEVICES, '') is None
    assert resolve_device_id(DEVICES, None) is None


def test_empty_or_none_device_list():
    assert resolve_device_id([], 'Phoniebox') is None
    assert resolve_device_id(None, 'Phoniebox') is None


def test_devices_without_name_are_skipped():
    devices = [{'id': 'x'}, {'id': 'y', 'name': None}, {'id': 'z', 'name': 'Phoniebox'}]
    assert resolve_device_id(devices, 'Phoniebox') == 'z'


def test_first_match_wins():
    devices = [{'id': 'first', 'name': 'Phoniebox'}, {'id': 'second', 'name': 'phoniebox'}]
    assert resolve_device_id(devices, 'Phoniebox') == 'first'
