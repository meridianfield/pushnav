"""Tests for Engine.retry_camera + the headless camera watchdog."""

import logging
import time

import pytest

import evf.engine.engine as engine_mod
from evf.config.manager import ConfigManager
from evf.engine.engine import Engine, _usb_video_device_present
from evf.engine.state import EngineState


class _FakeMgr:
    def __init__(self, running: bool, recovering: bool = False) -> None:
        self.running = running
        self.recovering = recovering
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    cfg = ConfigManager(config_dir=tmp_path / "evf-config")
    eng = Engine(dev_mode=False, config=cfg)
    eng.startup_attempts = 0
    eng.connect_on_attempt = 1  # startup_camera succeeds on this attempt

    def fake_startup_camera():
        eng.startup_attempts += 1
        connected = eng.startup_attempts >= eng.connect_on_attempt
        eng._subprocess_mgr = _FakeMgr(running=connected)

    monkeypatch.setattr(eng, "startup_camera", fake_startup_camera)
    monkeypatch.setattr(engine_mod, "_usb_video_device_present", lambda: True)
    yield eng
    eng._shutting_down.set()


def _wait_for(cond, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


# -- retry_camera -------------------------------------------------------------


def test_retry_noop_when_connected(engine):
    engine._subprocess_mgr = _FakeMgr(running=True)
    assert engine.retry_camera() is True
    assert engine.startup_attempts == 0


def test_retry_stops_stale_manager(engine):
    stale = _FakeMgr(running=False)
    engine._subprocess_mgr = stale
    assert engine.retry_camera() is True
    assert stale.stopped


def test_retry_returns_state_to_setup_after_recovery_gave_up(engine):
    sm = engine.state_machine
    sm.transition(EngineState.RECONNECTING)
    sm.transition(EngineState.ERROR)
    assert engine.retry_camera() is True
    assert sm.state == EngineState.SETUP


def test_retry_failure_leaves_state_alone(engine):
    engine.connect_on_attempt = 99
    sm = engine.state_machine
    sm.transition(EngineState.RECONNECTING)
    sm.transition(EngineState.ERROR)
    assert engine.retry_camera() is False
    assert sm.state == EngineState.ERROR


def test_retry_refused_once_shutting_down(engine):
    engine._shutting_down.set()
    assert engine.retry_camera() is False
    assert engine.startup_attempts == 0


# -- watchdog -------------------------------------------------------------------


def test_watchdog_retries_until_connected(engine):
    engine.connect_on_attempt = 3
    engine.start_camera_watchdog(interval_s=0.01)
    assert _wait_for(lambda: engine.camera_connected)
    time.sleep(0.1)
    assert engine.startup_attempts == 3  # stops retrying once connected


def test_watchdog_waits_without_usb_device(engine, monkeypatch, caplog):
    monkeypatch.setattr(engine_mod, "_usb_video_device_present", lambda: False)
    with caplog.at_level(logging.INFO, logger="evf.engine.engine"):
        engine.start_camera_watchdog(interval_s=0.01)
        time.sleep(0.15)
    assert engine.startup_attempts == 0
    waiting = [r for r in caplog.records if "Waiting for camera" in r.message]
    assert len(waiting) == 1  # logged once, not every tick


def test_watchdog_skips_while_manager_recovering(engine):
    engine._subprocess_mgr = _FakeMgr(running=False, recovering=True)
    engine.start_camera_watchdog(interval_s=0.01)
    time.sleep(0.15)
    assert engine.startup_attempts == 0


def test_watchdog_exits_on_shutdown(engine):
    engine.connect_on_attempt = 99
    engine.start_camera_watchdog(interval_s=0.01)
    engine._shutting_down.set()
    engine._camera_watchdog.join(timeout=1)
    assert not engine._camera_watchdog.is_alive()


# -- USB presence probe ---------------------------------------------------------


def _fake_sysfs(tmp_path, devices: dict[str, str]):
    """Build /sys/class/video4linux-like nodes whose `device` links to `devices[name]`."""
    root = tmp_path / "video4linux"
    root.mkdir()
    for name, target in devices.items():
        dev = tmp_path / target.lstrip("/")
        dev.mkdir(parents=True, exist_ok=True)
        (root / name).mkdir()
        (root / name / "device").symlink_to(dev)
    return root


def test_usb_probe_ignores_soc_video_blocks(tmp_path, monkeypatch):
    root = _fake_sysfs(tmp_path, {
        "video19": "/sys/devices/platform/axi/1000800000.codec",
        "video20": "/sys/devices/platform/axi/1000880000.pisp_be",
    })
    monkeypatch.setattr(engine_mod, "_V4L2_SYSFS", root)
    assert _usb_video_device_present() is False


def test_usb_probe_finds_usb_camera(tmp_path, monkeypatch):
    root = _fake_sysfs(tmp_path, {
        "video0": "/sys/devices/platform/axi/1f00300000.usb/xhci-hcd.1/usb3/3-2/3-2:1.0",
        "video20": "/sys/devices/platform/axi/1000880000.pisp_be",
    })
    monkeypatch.setattr(engine_mod, "_V4L2_SYSFS", root)
    assert _usb_video_device_present() is True


def test_usb_probe_without_sysfs_says_try(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_mod, "_V4L2_SYSFS", tmp_path / "missing")
    assert _usb_video_device_present() is True


# -- startup without a USB camera -------------------------------------------------


def test_startup_camera_skips_spawn_without_usb(tmp_path, monkeypatch, caplog):
    """No USB video device → no camera_server spawn, one info line, no errors."""

    def boom(*_a, **_k):
        raise AssertionError("SubprocessManager must not be created")

    monkeypatch.setattr(engine_mod, "_usb_video_device_present", lambda: False)
    monkeypatch.setattr(engine_mod, "SubprocessManager", boom)
    eng = Engine(dev_mode=False, config=ConfigManager(config_dir=tmp_path / "cfg"))
    try:
        with caplog.at_level(logging.INFO, logger="evf.engine.engine"):
            eng.startup_camera()
            eng.start_camera_watchdog(interval_s=0.01)
            time.sleep(0.1)
        assert not eng.camera_connected
        waiting = [r for r in caplog.records if "Waiting for camera" in r.message]
        assert len(waiting) == 1  # startup + watchdog ticks share one line
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    finally:
        eng._shutting_down.set()
