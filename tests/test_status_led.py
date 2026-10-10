"""Tests for the headless status LED: pattern mapping, LED discovery, driver."""

import os
import time

import pytest

from evf.engine import status_led as sl
from evf.engine.state import EngineState as S


# -- pattern mapping ------------------------------------------------------------


@pytest.mark.parametrize(
    "state,camera,failures,with_red,without_red",
    [
        (S.ERROR, True, 0, sl.RED_STEADY, sl.GREEN_STEADY),
        (S.ERROR, False, 0, sl.RED_STEADY, sl.GREEN_STEADY),  # error beats no-camera
        (S.SETUP, False, 0, sl.RED_SLOW_BLINK, sl.GREEN_DOUBLE_BLINK),
        (S.RECONNECTING, True, 0, sl.RED_SLOW_BLINK, sl.GREEN_DOUBLE_BLINK),
        (S.TRACKING, False, 0, sl.RED_SLOW_BLINK, sl.GREEN_DOUBLE_BLINK),
        (S.TRACKING, True, 0, sl.GREEN_BLIP, sl.GREEN_BLIP),
        (S.TRACKING, True, 2, sl.GREEN_BLIP, sl.GREEN_BLIP),
        (S.TRACKING, True, 3, sl.GREEN_FAST_BLINK, sl.GREEN_FAST_BLINK),
        (S.SETUP, True, 0, sl.GREEN_SLOW_BLINK, sl.GREEN_SLOW_BLINK),
        (S.SYNC, True, 5, sl.GREEN_SLOW_BLINK, sl.GREEN_SLOW_BLINK),
        (S.SYNC_CONFIRM, True, 0, sl.GREEN_SLOW_BLINK, sl.GREEN_SLOW_BLINK),
        (S.CALIBRATE, True, 0, sl.GREEN_SLOW_BLINK, sl.GREEN_SLOW_BLINK),
        (S.WARMING_UP, True, 0, sl.GREEN_SLOW_BLINK, sl.GREEN_SLOW_BLINK),
    ],
)
def test_pattern_for(state, camera, failures, with_red, without_red):
    assert sl.pattern_for(state, camera, failures, has_red=True) == with_red
    assert sl.pattern_for(state, camera, failures, has_red=False) == without_red


def test_green_only_patterns_are_all_distinct():
    green_only = {
        sl.pattern_for(s, c, f, has_red=False)
        for s, c, f in [(S.ERROR, True, 0), (S.SETUP, False, 0), (S.TRACKING, True, 3),
                        (S.TRACKING, True, 0), (S.SETUP, True, 0)]
    }
    assert len(green_only) == 5
    assert all(p.led == "green" for p in green_only)


# -- find_leds -------------------------------------------------------------------


def _sysfs(tmp_path, names, mode=0o664):
    root = tmp_path / "leds"
    for name in names:
        (root / name).mkdir(parents=True)
        b = root / name / "brightness"
        b.write_text("0")
        b.chmod(mode)
    return root


def test_find_leds_act_pwr(tmp_path):
    root = _sysfs(tmp_path, ["ACT", "PWR", "mmc0"])
    assert sl.find_leds(root) == {"green": root / "ACT/brightness", "red": root / "PWR/brightness"}


def test_find_leds_old_kernel_names(tmp_path):
    root = _sysfs(tmp_path, ["led0", "led1"])
    assert sl.find_leds(root) == {"green": root / "led0/brightness", "red": root / "led1/brightness"}


def test_find_leds_green_only(tmp_path):
    root = _sysfs(tmp_path, ["ACT"])
    assert sl.find_leds(root) == {"green": root / "ACT/brightness"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write read-only files")
def test_find_leds_skips_unwritable(tmp_path):
    root = _sysfs(tmp_path, ["ACT", "PWR"], mode=0o444)
    assert sl.find_leds(root) == {}


def test_find_leds_missing_root(tmp_path):
    assert sl.find_leds(tmp_path / "nope") == {}


# -- controller -------------------------------------------------------------------


class _FakeLed:
    def __init__(self, fail: bool = False) -> None:
        self.writes: list[tuple[float, str]] = []
        self.fail = fail

    def write_text(self, value: str) -> None:
        if self.fail:
            raise OSError("Permission denied")
        self.writes.append((time.monotonic(), value))

    @property
    def value(self) -> str | None:
        return self.writes[-1][1] if self.writes else None


class _Status:
    def __init__(self, state=S.SETUP, camera=True, failures=0):
        self.state, self.camera, self.failures = state, camera, failures

    def __call__(self):
        return self.state, self.camera, self.failures


def _controller(status, leds):
    c = sl.StatusLedController(status, leds, poll_s=0.01)
    c.start()
    return c


def _wait_for(cond, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return False


def test_controller_blinks_green_and_holds_red_off():
    green, red = _FakeLed(), _FakeLed()
    c = _controller(_Status(S.TRACKING, True, 3), {"green": green, "red": red})  # fast blink 0.1/0.1
    try:
        time.sleep(0.55)
    finally:
        c.stop()
    values = [v for _, v in green.writes]
    assert values == ["1", "0"] * 3  # 0.55 s of a 0.2 s cycle; already off at stop()
    gaps = [b - a for (a, _), (b, _) in zip(green.writes, green.writes[1:])]
    assert all(0.07 < g < 0.15 for g in gaps), gaps  # 0.1 s steps, no drift
    assert [v for _, v in red.writes] == ["0"]  # set off once, never rewritten


def test_controller_writes_only_on_change():
    green, red = _FakeLed(), _FakeLed()
    c = _controller(_Status(S.ERROR), {"green": green, "red": red})  # red steady
    try:
        time.sleep(0.2)  # ~20 polls
    finally:
        c.stop()
    assert [v for _, v in red.writes] == ["1", "0"]  # on, then off at stop()
    assert [v for _, v in green.writes] == ["0"]


def test_controller_follows_a_status_change():
    green, red = _FakeLed(), _FakeLed()
    status = _Status(S.SETUP, camera=False)  # red slow blink
    c = _controller(status, {"green": green, "red": red})
    try:
        assert _wait_for(lambda: red.value == "1")
        status.camera = True  # → green slow blink
        assert _wait_for(lambda: c.pattern == sl.GREEN_SLOW_BLINK, timeout=0.2)
        assert _wait_for(lambda: green.value == "1" and red.value == "0", timeout=0.2)
    finally:
        c.stop()


def test_controller_stop_turns_leds_off():
    green, red = _FakeLed(), _FakeLed()
    c = _controller(_Status(S.ERROR), {"green": green, "red": red})
    assert _wait_for(lambda: red.value == "1")
    c.stop()
    assert green.value == "0" and red.value == "0"
    assert not c._thread.is_alive()


def test_controller_disables_itself_on_write_error(caplog):
    green = _FakeLed(fail=True)
    c = _controller(_Status(S.SETUP), {"green": green})
    assert _wait_for(lambda: not c._thread.is_alive())
    assert any("Status LED disabled" in r.message for r in caplog.records)
    c.stop()


def test_controller_keeps_last_pattern_if_snapshot_fails():
    green = _FakeLed()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("engine shutting down")
        return S.ERROR, True, 0

    c = _controller(flaky, {"green": green})  # green steady (no red)
    try:
        time.sleep(0.1)
        assert c.pattern == sl.GREEN_STEADY and green.value == "1"
        assert c._thread.is_alive()
    finally:
        c.stop()


# -- root helper (take / restore) --------------------------------------------------

import grp
import json
import stat

from evf.engine import led_helper as lh


def _helper_sysfs(tmp_path, leds):
    """leds: {name: (trigger, brightness, mode)}"""
    root = tmp_path / "leds"
    for name, (trigger, brightness, mode) in leds.items():
        d = root / name
        d.mkdir(parents=True)
        (d / "trigger").write_text(
            " ".join(f"[{t}]" if t == trigger else t for t in ["none", "timer", "mmc0", "default-on"])
        )
        (d / "brightness").write_text(str(brightness))
        (d / "brightness").chmod(mode)
    return root


def _trigger(d):
    """Active trigger of a fake LED. Real sysfs always brackets it ("[mmc0]");
    a plain file just holds the last word written, e.g. "mmc0"."""
    text = (d / "trigger").read_text().strip()
    return lh._current_trigger(d) if "[" in text else text


def _snapshot(root):
    return {
        d.name: (_trigger(d), (d / "brightness").read_text().strip(),
                 stat.S_IMODE((d / "brightness").stat().st_mode))
        for d in sorted(root.iterdir())
    }


_MY_GROUP = grp.getgrgid(os.getgid()).gr_name


def test_take_then_restore_round_trip(tmp_path):
    root = _helper_sysfs(tmp_path, {"ACT": ("mmc0", 0, 0o644), "PWR": ("default-on", 1, 0o644)})
    before = _snapshot(root)
    state = tmp_path / "state"

    lh.take(root, state, _MY_GROUP)
    for name in ("ACT", "PWR"):
        assert _trigger(root / name) == "none"
        assert (root / name / "brightness").read_text() == "0"
        assert (root / name / "brightness").stat().st_mode & stat.S_IWGRP
    assert sorted(p.name for p in state.iterdir()) == ["ACT.json", "PWR.json"]

    lh.restore(root, state)
    assert _snapshot(root) == before
    assert list(state.iterdir()) == []


def test_second_take_keeps_the_original_state(tmp_path):
    root = _helper_sysfs(tmp_path, {"ACT": ("mmc0", 0, 0o644)})
    state = tmp_path / "state"
    lh.take(root, state, _MY_GROUP)
    lh.take(root, state, _MY_GROUP)  # e.g. restart without a restore in between
    assert json.loads((state / "ACT.json").read_text())["trigger"] == "mmc0"
    lh.restore(root, state)
    assert _trigger(root / "ACT") == "mmc0"


def test_restore_without_state_is_a_noop(tmp_path):
    root = _helper_sysfs(tmp_path, {"ACT": ("mmc0", 0, 0o644)})
    before = _snapshot(root)
    lh.restore(root, tmp_path / "missing-state")
    assert _snapshot(root) == before


def test_take_handles_green_only_and_old_names(tmp_path):
    root = _helper_sysfs(tmp_path, {"led0": ("mmc0", 0, 0o644)})
    state = tmp_path / "state"
    lh.take(root, state, _MY_GROUP)
    assert [p.name for p in state.iterdir()] == ["led0.json"]
    lh.restore(root, state)
    assert _trigger(root / "led0") == "mmc0"


@pytest.mark.parametrize("config,expected", [
    (None, True),                                   # no config file yet
    ({"led": {"enabled": True}}, True),
    ({"led": {"enabled": False}}, False),
    ({"version": 1}, True),                         # older config without the key
    ("not json", True),
])
def test_led_enabled(tmp_path, config, expected):
    path = tmp_path / "config.json"
    if config is not None:
        path.write_text(config if isinstance(config, str) else json.dumps(config))
    assert lh.led_enabled(path) is expected
    if config is None:
        assert not path.exists()  # never creates the config as root


def test_main_take_respects_disabled_config(tmp_path):
    root = _helper_sysfs(tmp_path, {"ACT": ("mmc0", 0, 0o644)})
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"led": {"enabled": False}}))
    state = tmp_path / "state"
    rc = lh.main(["take", "--group", _MY_GROUP, "--root", str(root),
                  "--state-dir", str(state), "--config", str(cfg)])
    assert rc == 0
    assert _trigger(root / "ACT") == "mmc0"
    assert not state.exists()


def test_main_never_fails(tmp_path):
    root = _helper_sysfs(tmp_path, {"ACT": ("mmc0", 0, 0o644)})
    rc = lh.main(["take", "--group", "no-such-group-xyz", "--root", str(root),
                  "--state-dir", str(tmp_path / "state"), "--config", str(tmp_path / "c.json")])
    assert rc == 0  # unknown group → logged, service still starts
