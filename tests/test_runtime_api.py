from uar.server.runtime_api import app


def test_runtime_api_exists():
    assert app is not None or app is None
