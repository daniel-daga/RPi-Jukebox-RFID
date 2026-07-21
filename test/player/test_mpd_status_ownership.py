import importlib.util
import pathlib
import sys
import types
from enum import Enum
from unittest.mock import Mock, call


def _identity_decorator(function):
    return function


def _load_playermpd_module():
    """Load playermpd without starting MPD, timers, or the jukebox daemon."""
    components = types.ModuleType('components')
    components.__path__ = []
    player = types.ModuleType('components.player')
    player.arbiter = Mock()
    components.player = player

    jukebox = types.ModuleType('jukebox')
    jukebox.__path__ = []
    cfghandler = types.ModuleType('jukebox.cfghandler')
    cfghandler.get_handler = Mock(return_value=Mock())
    utils = types.ModuleType('jukebox.utils')
    plugs = types.ModuleType('jukebox.plugs')
    plugs.tag = _identity_decorator
    plugs.initialize = _identity_decorator
    plugs.atexit = _identity_decorator
    multitimer = types.ModuleType('jukebox.multitimer')
    publishing = types.ModuleType('jukebox.publishing')
    publishing.get_publisher = Mock(return_value=Mock())
    playlistgenerator = types.ModuleType('jukebox.playlistgenerator')
    nvmanager = types.ModuleType('jukebox.NvManager')
    nvmanager.nv_manager = Mock()
    jukebox.cfghandler = cfghandler
    jukebox.utils = utils
    jukebox.plugs = plugs
    jukebox.multitimer = multitimer
    jukebox.publishing = publishing
    jukebox.playlistgenerator = playlistgenerator

    misc = types.ModuleType('misc')

    package_name = 'playermpd_under_test'
    playcontentcallback = types.ModuleType(f'{package_name}.playcontentcallback')

    class PlayCardState(Enum):
        firstSwipe = 0
        secondSwipe = 1

    class PlayContentCallbacks:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    playcontentcallback.PlayCardState = PlayCardState
    playcontentcallback.PlayContentCallbacks = PlayContentCallbacks

    coverart = types.ModuleType(f'{package_name}.coverart_cache_manager')
    coverart.CoverartCacheManager = Mock

    stubs = {
        'components': components,
        'components.player': player,
        'jukebox': jukebox,
        'jukebox.cfghandler': cfghandler,
        'jukebox.utils': utils,
        'jukebox.plugs': plugs,
        'jukebox.multitimer': multitimer,
        'jukebox.publishing': publishing,
        'jukebox.playlistgenerator': playlistgenerator,
        'jukebox.NvManager': nvmanager,
        'misc': misc,
        f'{package_name}.playcontentcallback': playcontentcallback,
        f'{package_name}.coverart_cache_manager': coverart,
    }
    previous = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)

    module_path = (pathlib.Path(__file__).resolve().parents[2]
                   / 'src' / 'jukebox' / 'components' / 'playermpd' / '__init__.py')
    spec = importlib.util.spec_from_file_location(
        package_name, module_path, submodule_search_locations=[str(module_path.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(package_name, None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
    return module


player_module = _load_playermpd_module()
PlayerMPD = player_module.PlayerMPD


def _bare_player():
    player_module.components.player.arbiter.reset_mock()
    player_module.publishing.get_publisher.reset_mock()
    player_module.publishing.get_publisher.return_value.reset_mock()
    player = PlayerMPD.__new__(PlayerMPD)
    player.mpd_status = {}
    player.current_folder_status = {}
    player.music_player_status = {'player_status': {}}
    player.mpd_client = Mock()
    player.mpd_retry_with_mutex = Mock(side_effect=[{}, {}])
    return player


def test_inactive_mpd_polls_status_without_publishing():
    player = _bare_player()
    publisher = player_module.publishing.get_publisher.return_value
    player_module.components.player.arbiter.is_active.return_value = False

    player._mpd_status_poll()

    assert player.mpd_retry_with_mutex.call_args_list == [
        call(player.mpd_client.status),
        call(player.mpd_client.currentsong),
    ]
    player_module.publishing.get_publisher.assert_not_called()
    publisher.send.assert_not_called()


def test_active_mpd_publishes_owned_status_once():
    player = _bare_player()
    publisher = player_module.publishing.get_publisher.return_value
    player_module.components.player.arbiter.is_active.return_value = True

    player._mpd_status_poll()

    player_module.publishing.get_publisher.assert_called_once_with()
    publisher.send.assert_called_once_with(
        'playerstatus',
        {'player': 'mpd'},
    )
