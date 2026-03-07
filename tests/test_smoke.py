"""Smoke tests — verifies the wsnsim package and all submodules can be imported."""
import wsnsim
import wsnsim.sim
import wsnsim.models
import wsnsim.scenarios
import wsnsim.metrics
import wsnsim.utils


def test_package_version():
    assert wsnsim.__version__ == "0.1.0"


def test_submodules_importable():
    """All top-level submodules must be importable without errors."""
    for mod in (wsnsim.sim, wsnsim.models, wsnsim.scenarios, wsnsim.metrics, wsnsim.utils):
        assert mod is not None
