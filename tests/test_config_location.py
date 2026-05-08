"""Tests for ConfigManager.location."""

import pytest

from evf.config.manager import ConfigManager


def test_location_default_is_none(tmp_path):
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    assert cfg.location is None


def test_location_roundtrip(tmp_path):
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    cfg.location = (13.0878, 80.2785)
    assert cfg.location == (13.0878, 80.2785)
    # Persists on disk
    cfg2 = ConfigManager(config_dir=tmp_path / "evf-config")
    assert cfg2.location == (13.0878, 80.2785)


def test_location_clear(tmp_path):
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    cfg.location = (13.0878, 80.2785)
    cfg.location = None
    assert cfg.location is None


def test_location_validates_range(tmp_path):
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    with pytest.raises(ValueError):
        cfg.location = (91.0, 0.0)
    with pytest.raises(ValueError):
        cfg.location = (0.0, 181.0)
    with pytest.raises(ValueError):
        cfg.location = (-91.0, 0.0)
    with pytest.raises(ValueError):
        cfg.location = (0.0, -181.0)
