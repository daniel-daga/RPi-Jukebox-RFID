import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def player_module():
    """Load the player module without initializing the application's config."""
    fake_jukebox = ModuleType("jukebox")
    fake_jukebox.__path__ = []
    fake_cfghandler = ModuleType("jukebox.cfghandler")
    fake_cfghandler.get_handler = lambda _name: object()
    fake_jukebox.cfghandler = fake_cfghandler

    previous_jukebox = sys.modules.get("jukebox")
    previous_cfghandler = sys.modules.get("jukebox.cfghandler")
    sys.modules["jukebox"] = fake_jukebox
    sys.modules["jukebox.cfghandler"] = fake_cfghandler

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "jukebox"
        / "components"
        / "player"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("player_arbiter_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        if previous_jukebox is None:
            sys.modules.pop("jukebox", None)
        else:
            sys.modules["jukebox"] = previous_jukebox
        if previous_cfghandler is None:
            sys.modules.pop("jukebox.cfghandler", None)
        else:
            sys.modules["jukebox.cfghandler"] = previous_cfghandler


@pytest.fixture
def arbiter(player_module):
    return player_module.PlayerArbiter()


class Backend:
    def __init__(self):
        self.deactivations = 0
        self.calls = []

    def on_deactivate(self):
        self.deactivations += 1

    def command(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "result"


def test_defaults_to_mpd_without_an_explicit_claim(arbiter):
    assert arbiter.active_name == "mpd"
    assert arbiter.is_active("mpd") is True
    assert arbiter.is_active("spotify") is False
    assert arbiter.route_from_default("play") == (False, None)


def test_registered_active_backend_receives_routed_call_exactly_once(arbiter):
    backend = Backend()
    arbiter.register_backend("spotify", backend)
    arbiter.claim_active("spotify")

    routed, result = arbiter.route_from_default("command", "track", repeat=True)

    assert routed is True
    assert result == "result"
    assert backend.calls == [(('track',), {"repeat": True})]


def test_claim_deactivates_other_registered_backends_but_not_active_backend(arbiter):
    mpd = Backend()
    spotify = Backend()
    auxiliary = Backend()
    arbiter.register_backend("mpd", mpd)
    arbiter.register_backend("spotify", spotify)
    arbiter.register_backend("auxiliary", auxiliary)

    arbiter.claim_active("spotify")

    assert arbiter.active_name == "spotify"
    assert mpd.deactivations == 1
    assert spotify.deactivations == 0
    assert auxiliary.deactivations == 1

    arbiter.claim_active("spotify")
    assert mpd.deactivations == 1
    assert auxiliary.deactivations == 1

    arbiter.claim_active("mpd")
    assert spotify.deactivations == 1
    assert auxiliary.deactivations == 2


def test_deactivation_failure_does_not_prevent_other_backends_deactivating(arbiter):
    class BrokenBackend(Backend):
        def on_deactivate(self):
            self.deactivations += 1
            raise RuntimeError("cannot deactivate")

    broken = BrokenBackend()
    healthy = Backend()
    target = Backend()
    arbiter.register_backend("broken", broken)
    arbiter.register_backend("healthy", healthy)
    arbiter.register_backend("spotify", target)

    arbiter.claim_active("spotify")

    assert broken.deactivations == 1
    assert healthy.deactivations == 1
    assert target.deactivations == 0


def test_missing_active_backend_is_not_reported_as_routed(arbiter):
    arbiter.claim_active("unregistered")

    assert arbiter.active_name == "unregistered"
    assert arbiter.route_from_default("play") == (False, None)


def test_missing_method_is_consumed_by_registered_active_backend(arbiter):
    arbiter.register_backend("spotify", Backend())
    arbiter.claim_active("spotify")

    assert arbiter.route_from_default("missing_method") == (True, None)


def test_routed_backend_exception_is_contained(arbiter):
    class BrokenBackend:
        def explode(self):
            raise ValueError("boom")

    arbiter.register_backend("spotify", BrokenBackend())
    arbiter.claim_active("spotify")

    assert arbiter.route_from_default("explode") == (True, None)


def test_interleaved_publishers_have_exactly_one_status_owner(arbiter):
    class Publisher(Backend):
        def __init__(self, name):
            super().__init__()
            self.name = name
            self.published = 0

        def poll_and_publish(self):
            if arbiter.is_active(self.name):
                self.published += 1
                return True
            return False

    mpd = Publisher("mpd")
    spotify = Publisher("spotify")
    arbiter.register_backend("mpd", mpd)
    arbiter.register_backend("spotify", spotify)

    assert (mpd.poll_and_publish(), spotify.poll_and_publish()) == (True, False)

    arbiter.claim_active("spotify")
    assert mpd.deactivations == 1
    assert (mpd.poll_and_publish(), spotify.poll_and_publish()) == (False, True)

    arbiter.claim_active("mpd")
    assert spotify.deactivations == 1
    assert (spotify.poll_and_publish(), mpd.poll_and_publish()) == (False, True)
    assert mpd.published == 2
    assert spotify.published == 1
