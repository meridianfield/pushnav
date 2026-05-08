"""Tests for engine location resolution + setter."""

from unittest.mock import MagicMock

from evf.engine.engine import Engine


def test_location_none_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    eng = Engine(dev_mode=False)
    eng._config._dir = tmp_path / "evf-config"
    eng._config._path = eng._config._dir / "config.json"
    assert eng.location == {"latitude": None, "longitude": None, "source": None}


def test_location_from_manual_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    eng = Engine(dev_mode=False)
    eng._config._dir = tmp_path / "evf-config"
    eng._config._path = eng._config._dir / "config.json"
    eng.set_location(13.0878, 80.2785)
    assert eng.location == {
        "latitude": 13.0878,
        "longitude": 80.2785,
        "source": "manual",
    }


def test_location_from_stellarium_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    eng = Engine(dev_mode=False)
    eng._config._dir = tmp_path / "evf-config"
    eng._config._path = eng._config._dir / "config.json"
    eng.set_location(13.0878, 80.2785)  # manual

    # Mock a Stellarium server with a location
    fake_server = MagicMock()
    fake_server.stellarium_status = {
        "location": {"name": "London", "latitude": 51.5, "longitude": -0.1},
    }
    eng._stellarium = fake_server

    loc = eng.location
    assert loc["source"] == "stellarium"
    assert loc["latitude"] == 51.5
    assert loc["longitude"] == -0.1


def test_set_location_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    eng = Engine(dev_mode=False)
    eng._config._dir = tmp_path / "evf-config"
    eng._config._path = eng._config._dir / "config.json"
    eng.set_location(13.0878, 80.2785)
    eng.set_location(None, None)
    assert eng.location == {"latitude": None, "longitude": None, "source": None}
