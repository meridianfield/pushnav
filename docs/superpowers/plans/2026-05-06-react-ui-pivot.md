# React/ShadCN UI Pivot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 1,896-line DearPyGui desktop UI (`python/evf/ui/window.py`) with a React + ShadCN front-end hosted in a pywebview window, while keeping the engine, solver, and TCP servers unchanged.

**Architecture:** The engine's existing aiohttp server gains an MJPEG frame endpoint and `POST /api/*` action endpoints. A new `web/` directory holds a Vite + React + TS + Tailwind + shadcn front-end. In dev, Vite serves on `:5173` with HMR and proxies to the Python engine on `:8080`. In prod, Nuitka bundles the React build (`web/dist/`) and pywebview opens a native window pointing at `http://localhost:8080`. DPG and React run side-by-side until feature parity is reached, then DPG is removed.

**Tech Stack:** Python 3.12, aiohttp, pywebview ≥ 5.0, Node 20+, Vite 5, React 18, TypeScript 5, Tailwind 3, shadcn/ui (Radix + Tailwind), vitest, React Testing Library.

**Spec:** [`docs/superpowers/specs/2026-05-06-react-ui-pivot-design.md`](../specs/2026-05-06-react-ui-pivot-design.md)

---

## Phase 1 — Engine API extensions (Python)

Build the new HTTP/WS surface that the React app will consume. DPG keeps working throughout.

### Task 1: MJPEG frame endpoint

**Files:**
- Modify: `python/evf/webserver/server.py`
- Create: `tests/test_webserver_mjpeg.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_webserver_mjpeg.py`:

```python
"""Tests for the MJPEG frame stream endpoint."""

import asyncio
import threading
from typing import AsyncIterator

import pytest
from aiohttp import ClientSession

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer

# 1x1 px JPEG (smallest valid JPEG)
_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606"
    "0706050807070709090808 0a 0c 14 0d 0c 0b 0b 0c 19 12 13 0f 14"
).replace(b" ", b"")


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Start a WebServer on an ephemeral port for testing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = ConfigManager()
    cfg.web_port = 0  # ephemeral
    fb = LatestFrame()
    fb.put(_TINY_JPEG)
    ws = WebServer(PointingState(), StateMachine(), GotoTarget(), cfg, frame_buffer=fb)
    ws.start()
    # Wait briefly for thread to bind
    for _ in range(20):
        if ws._port is not None:
            break
        threading.Event().wait(0.05)
    yield ws
    ws.stop()


@pytest.mark.asyncio
async def test_mjpeg_returns_multipart_with_jpeg_part(server):
    async with ClientSession() as s:
        async with s.get(f"http://127.0.0.1:{server._port}/frame.mjpg") as resp:
            assert resp.status == 200
            assert "multipart/x-mixed-replace" in resp.headers["Content-Type"]
            # Read first part: should contain a JPEG SOI marker (0xFFD8)
            chunk = await resp.content.read(4096)
            assert b"\xff\xd8" in chunk
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_webserver_mjpeg.py -v
```

Expected: FAIL — `WebServer.__init__()` got an unexpected keyword argument `frame_buffer`, or 404 on `/frame.mjpg`.

- [ ] **Step 3: Add `frame_buffer` parameter to `WebServer.__init__`**

In `python/evf/webserver/server.py`, modify `WebServer.__init__` to accept and store a `LatestFrame`:

```python
def __init__(
    self,
    pointing: PointingState,
    state_machine: StateMachine,
    goto_target: GotoTarget,
    config: ConfigManager,
    *,
    frame_buffer=None,                  # NEW
    solver_failures: Callable[[], int] | None = None,
    stellarium_object: Callable[[], dict | None] | None = None,
) -> None:
    self._pointing = pointing
    self._state_machine = state_machine
    self._goto_target = goto_target
    self._config = config
    self._frame_buffer = frame_buffer    # NEW
    self._solver_failures = solver_failures
    self._stellarium_object = stellarium_object

    self._clients: set[web.WebSocketResponse] = set()
    self._loop: asyncio.AbstractEventLoop | None = None
    self._thread: threading.Thread | None = None
    self._url: str | None = None
    self._port: int | None = None        # NEW — for tests on ephemeral port
```

Inside `_serve()`, after `await site.start()`, also store the actual port:

```python
self._port = site._server.sockets[0].getsockname()[1]
```

- [ ] **Step 4: Add MJPEG handler**

Append to `WebServer` class in `python/evf/webserver/server.py`:

```python
_MJPEG_BOUNDARY = b"frame"
_MJPEG_INTERVAL = 0.1  # 10 Hz

async def _handle_mjpeg(self, request: web.Request) -> web.StreamResponse:
    """Multipart MJPEG stream of the latest camera frame."""
    if self._frame_buffer is None:
        return web.Response(status=503, text="No frame buffer")
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={self._MJPEG_BOUNDARY.decode()}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
    await resp.prepare(request)
    last_frame_id = -1
    try:
        while True:
            jpeg, _ts, fid = self._frame_buffer.get()
            if jpeg is not None and fid != last_frame_id:
                last_frame_id = fid
                part = (
                    b"--" + self._MJPEG_BOUNDARY + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg + b"\r\n"
                )
                await resp.write(part)
            await asyncio.sleep(self._MJPEG_INTERVAL)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    return resp
```

Register the route in `_serve()` (just below `/ws`):

```python
app.router.add_get("/frame.mjpg", self._handle_mjpeg)
```

- [ ] **Step 5: Wire `frame_buffer` from engine**

In `python/evf/engine/engine.py`, `startup_webserver()`, pass the frame buffer:

```python
self._webserver = WebServer(
    self._pointing_state,
    self._state_machine,
    self._goto_target,
    self._config,
    frame_buffer=self._frame_buffer,   # NEW
    stellarium_object=lambda: self.stellarium_object,
)
```

- [ ] **Step 6: Add pytest-asyncio dev dependency**

Modify `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "nuitka>=4.0.2",
    "pytest",
    "pytest-asyncio>=0.23",
]
```

Add to `pyproject.toml` (top level):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Run `uv sync`.

- [ ] **Step 7: Run test to verify it passes**

```bash
uv run pytest tests/test_webserver_mjpeg.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add python/evf/webserver/server.py python/evf/engine/engine.py \
        tests/test_webserver_mjpeg.py pyproject.toml uv.lock
git commit -m "feat(webserver): add MJPEG frame endpoint at /frame.mjpg

10 Hz multipart/x-mixed-replace stream sourced from frame_buffer.
Browsers and OS webviews render this natively in <img>; no JS decode."
```

---

### Task 2: Extend `/ws` payload with control + sync + activity fields

**Files:**
- Modify: `python/evf/webserver/server.py:231-266` (`_build_payload`)
- Modify: `python/evf/engine/engine.py` — pass extra callables to WebServer
- Create: `tests/test_webserver_payload.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_webserver_payload.py`:

```python
"""Tests for /ws JSON payload schema."""

import json

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer


def test_payload_contains_new_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = WebServer(
        PointingState(), StateMachine(), GotoTarget(), ConfigManager(),
        frame_buffer=LatestFrame(),
        camera_controls=lambda: [
            {"id": "exposure", "label": "Exposure", "min": 0, "max": 100, "step": 1, "value": 50, "unit": "ms"},
        ],
        sync_state=lambda: {
            "in_progress": False, "candidates": [], "selected_idx": None, "error": None,
        },
        activity=lambda: {
            "stellarium": {"active": False, "address": "localhost:10001"},
            "lx200":      {"active": False, "address": "0.0.0.0:4030"},
            "webserver":  {"url": "http://192.168.1.42:8080"},
            "audio_enabled": True,
        },
    )
    payload = ws._build_payload()
    # Existing fields still present
    assert "state" in payload
    assert "pointing" in payload
    # New fields
    assert "controls" in payload and isinstance(payload["controls"], list)
    assert "sync" in payload and "in_progress" in payload["sync"]
    assert "stellarium" in payload and "active" in payload["stellarium"]
    assert "lx200" in payload
    assert "webserver" in payload
    assert "audio_enabled" in payload
    assert "camera" in payload  # centroid arrays
    # Roundtrip JSON-serializable
    assert json.dumps(payload)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_webserver_payload.py -v
```

Expected: FAIL — unknown kwargs or missing fields.

- [ ] **Step 3: Add new optional callables to `WebServer.__init__`**

In `python/evf/webserver/server.py`:

```python
def __init__(
    self,
    pointing: PointingState,
    state_machine: StateMachine,
    goto_target: GotoTarget,
    config: ConfigManager,
    *,
    frame_buffer=None,
    solver_failures: Callable[[], int] | None = None,
    stellarium_object: Callable[[], dict | None] | None = None,
    camera_controls: Callable[[], list[dict] | None] | None = None,   # NEW
    sync_state: Callable[[], dict] | None = None,                     # NEW
    activity: Callable[[], dict] | None = None,                       # NEW
) -> None:
    # ...store all of the above on self
    self._camera_controls = camera_controls
    self._sync_state = sync_state
    self._activity = activity
```

- [ ] **Step 4: Extend `_build_payload`**

Modify `_build_payload` in `python/evf/webserver/server.py` to add the new fields. Add this block before `return {...}`:

```python
controls = self._camera_controls() if self._camera_controls else []
sync_blk = self._sync_state() if self._sync_state else {
    "in_progress": False, "candidates": [], "selected_idx": None, "error": None,
}
activity_blk = self._activity() if self._activity else {}
camera_blk = {
    "connected": True if (self._frame_buffer and self._frame_buffer.get()[0]) else False,
    "all_centroids": snap.all_centroids if snap.valid else None,
    "matched_centroids": snap.matched_centroids if snap.valid else None,
}
```

Then in the final `return {...}` dict, add:

```python
"controls": controls or [],
"sync": sync_blk,
"stellarium": activity_blk.get("stellarium", {"active": False, "address": None}),
"lx200":      activity_blk.get("lx200",      {"active": False, "address": None}),
"webserver":  activity_blk.get("webserver",  {"url": None}),
"audio_enabled": activity_blk.get("audio_enabled", True),
"camera": camera_blk,
```

- [ ] **Step 5: Wire engine → WebServer**

In `python/evf/engine/engine.py`, `startup_webserver()`, pass the new callables:

```python
self._webserver = WebServer(
    self._pointing_state,
    self._state_machine,
    self._goto_target,
    self._config,
    frame_buffer=self._frame_buffer,
    stellarium_object=lambda: self.stellarium_object,
    camera_controls=lambda: self.camera_controls,
    sync_state=lambda: {
        "in_progress": self.sync_in_progress,
        "candidates": [
            {"idx": i, "name": c.name, "ra_deg": c.ra, "dec_deg": c.dec, "magnitude": c.mag}
            for i, c in enumerate(self.sync_candidates or [])
        ],
        "selected_idx": self.sync_selected_idx,
        "error": self.sync_error,
    },
    activity=lambda: {
        "stellarium": {
            "active": self.stellarium_has_client,
            "address": self.stellarium_address,
            "status": self.stellarium_status,
            "object": self.stellarium_object,
        },
        "lx200": {
            "active": self.lx200_active,
            "address": self.lx200_address,
        },
        "webserver": {"url": self.web_url},
        "audio_enabled": self.audio_enabled,
    },
)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_webserver_payload.py tests/test_webserver_mjpeg.py -v
```

Expected: PASS for both.

- [ ] **Step 7: Commit**

```bash
git add python/evf/webserver/server.py python/evf/engine/engine.py \
        tests/test_webserver_payload.py
git commit -m "feat(webserver): extend /ws payload with controls, sync, activity

Adds fields the React UI needs that today only DPG window.py had access to:
camera control descriptors, sync candidate list, Stellarium/LX200/web URL,
audio enabled flag, centroid arrays."
```

---

### Task 3: `POST /api/*` action endpoints

**Files:**
- Modify: `python/evf/webserver/server.py` — add handlers + routes
- Create: `tests/test_webserver_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_webserver_api.py`:

```python
"""Tests for POST /api/* action endpoints."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientSession

from evf.config.manager import ConfigManager
from evf.engine.frame_buffer import LatestFrame
from evf.engine.goto_target import GotoTarget
from evf.engine.pointing import PointingState
from evf.engine.state import StateMachine
from evf.webserver.server import WebServer


@pytest.fixture
def server_and_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = ConfigManager()
    cfg.web_port = 0
    actions = MagicMock()
    ws = WebServer(
        PointingState(), StateMachine(), GotoTarget(), cfg,
        frame_buffer=LatestFrame(),
        actions=actions,
    )
    ws.start()
    for _ in range(20):
        if ws._port is not None:
            break
        threading.Event().wait(0.05)
    yield ws, actions
    ws.stop()


@pytest.mark.asyncio
async def test_wizard_advance(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/wizard/advance") as resp:
            assert resp.status == 204
    actions.step_advance.assert_called_once()


@pytest.mark.asyncio
async def test_sync_select_with_idx(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/sync/select", json={"idx": 2}) as resp:
            assert resp.status == 204
    actions.set_sync_selected.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_set_control(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/control",
                          json={"name": "exposure", "value": 42}) as resp:
            assert resp.status == 204
    actions.set_control.assert_called_once_with("exposure", 42)


@pytest.mark.asyncio
async def test_settings_audio(server_and_actions):
    ws, actions = server_and_actions
    async with ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{ws._port}/api/settings",
                          json={"audio_enabled": False}) as resp:
            assert resp.status == 204
    actions.set_audio_enabled.assert_called_once_with(False)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_webserver_api.py -v
```

Expected: FAIL — unknown `actions` kwarg or 404 on POST routes.

- [ ] **Step 3: Define the EngineActions interface**

In `python/evf/webserver/server.py`, add at module top (after imports):

```python
from typing import Protocol


class EngineActions(Protocol):
    """Action surface the WebServer calls into. Implemented by Engine."""

    def step_advance(self) -> None: ...
    def sync_retry(self) -> None: ...
    def set_sync_selected(self, idx: int) -> None: ...
    def use_previous_calibration(self) -> None: ...
    def set_control(self, name: str, value: int) -> None: ...
    def clear_goto_target(self) -> None: ...
    def set_audio_enabled(self, enabled: bool) -> None: ...
    def set_hidpi(self, enabled: bool) -> None: ...
```

Add `actions: EngineActions | None = None` to `WebServer.__init__`, store as `self._actions`.

- [ ] **Step 4: Add API handlers**

Append to `WebServer` in `python/evf/webserver/server.py`:

```python
async def _handle_api(self, request: web.Request, fn) -> web.Response:
    """Run a synchronous engine action and return 204."""
    if self._actions is None:
        return web.Response(status=503, text="No actions wired")
    try:
        await asyncio.get_event_loop().run_in_executor(None, fn)
    except Exception as exc:
        logger.exception("API action failed: %s", exc)
        return web.Response(status=500, text=str(exc))
    return web.Response(status=204)

async def _api_wizard_advance(self, request):
    return await self._handle_api(request, self._actions.step_advance)

async def _api_sync_retry(self, request):
    return await self._handle_api(request, self._actions.sync_retry)

async def _api_sync_select(self, request):
    body = await request.json()
    idx = int(body["idx"])
    return await self._handle_api(request, lambda: self._actions.set_sync_selected(idx))

async def _api_use_previous_calibration(self, request):
    return await self._handle_api(request, self._actions.use_previous_calibration)

async def _api_set_control(self, request):
    body = await request.json()
    name = str(body["name"])
    value = int(body["value"])
    return await self._handle_api(request, lambda: self._actions.set_control(name, value))

async def _api_goto_clear(self, request):
    return await self._handle_api(request, self._actions.clear_goto_target)

async def _api_settings(self, request):
    body = await request.json()
    if "audio_enabled" in body:
        await self._handle_api(request, lambda: self._actions.set_audio_enabled(bool(body["audio_enabled"])))
    if "hidpi" in body:
        await self._handle_api(request, lambda: self._actions.set_hidpi(bool(body["hidpi"])))
    return web.Response(status=204)
```

Register routes in `_serve()`:

```python
app.router.add_post("/api/wizard/advance", self._api_wizard_advance)
app.router.add_post("/api/sync/retry", self._api_sync_retry)
app.router.add_post("/api/sync/select", self._api_sync_select)
app.router.add_post("/api/calibration/use-previous", self._api_use_previous_calibration)
app.router.add_post("/api/control", self._api_set_control)
app.router.add_post("/api/goto/clear", self._api_goto_clear)
app.router.add_post("/api/settings", self._api_settings)
```

- [ ] **Step 5: Add `set_audio_enabled` and `set_hidpi` methods to Engine**

In `python/evf/engine/engine.py`:

```python
def set_audio_enabled(self, enabled: bool) -> None:
    self.audio_enabled = enabled

def set_hidpi(self, enabled: bool) -> None:
    self._config.hidpi = enabled
```

- [ ] **Step 6: Wire `actions=self` into WebServer**

In `engine.py`, `startup_webserver`, add `actions=self` to the `WebServer(...)` call.

- [ ] **Step 7: Run test to verify it passes**

```bash
uv run pytest tests/test_webserver_api.py -v
```

Expected: PASS for all four tests.

- [ ] **Step 8: Commit**

```bash
git add python/evf/webserver/server.py python/evf/engine/engine.py \
        tests/test_webserver_api.py
git commit -m "feat(webserver): add POST /api/* action endpoints

Wizard, sync select/retry, calibration reuse, camera controls, GOTO clear,
settings (audio, hidpi). Engine exposes EngineActions protocol; WebServer
routes HTTP POSTs through asyncio.run_in_executor."
```

---

### Task 4: Add `--no-window` mode to `main.py` for dev workflow

**Files:**
- Modify: `python/evf/main.py`

- [ ] **Step 1: Add `--no-window` flag handling**

In `python/evf/main.py`, near `dev_mode = "--dev" in sys.argv`, add:

```python
no_window = "--no-window" in sys.argv
```

- [ ] **Step 2: Skip DPG entirely when `--no-window` is set**

Wrap the entire DPG block in `main()` such that when `no_window` is True, the engine starts but no window is shown. The simplest path: keep DPG behavior under `if not no_window:`, and when `no_window` is set, replace the `ui.run()` event loop with a blocking wait on a shutdown signal.

Add at module top:

```python
import signal
import threading
```

Replace the `ui.run()` line with:

```python
if no_window:
    logger.info("Running headless (--no-window). Press Ctrl-C to exit.")
    stop = threading.Event()

    def _handle_signal(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    stop.wait()
else:
    ui.run()  # DearPyGui event loop — blocks until window close
```

When `no_window` is True, also skip the entire `dpg.create_context() / create_viewport / ui.setup() / etc.` setup. Easiest: at the top of `main()`, after engine is created, add:

```python
if no_window:
    engine.startup_logging()
    engine.startup_solver()
    engine.startup_stellarium()
    engine.startup_lx200()
    engine.startup_webserver()
    engine.startup_camera()
    if engine.camera_connected:
        engine.startup_solver_thread()

    logger.info("Running headless (--no-window). Press Ctrl-C to exit.")
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    stop.wait()
    engine.shutdown()
    return
```

- [ ] **Step 3: Manual smoke test**

```bash
uv run python -m evf.main --dev --no-window
# In another terminal:
curl -s http://localhost:8080/api/wizard/advance -X POST
# Should return 204 (no body). Engine logs should show wizard advance.
# Ctrl-C in first terminal — clean shutdown.
```

- [ ] **Step 4: Commit**

```bash
git add python/evf/main.py
git commit -m "feat(main): add --no-window mode for headless dev/testing

Runs engine + servers without DPG, blocks until SIGINT/SIGTERM.
Used by the React dev workflow: Vite serves UI on :5173 and proxies
to the Python engine on :8080."
```

---

## Phase 2 — React + ShadCN scaffold

### Task 5: Initialize Vite + React + TypeScript project

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/index.css`
- Modify: `.gitignore`

- [ ] **Step 1: Verify Node 20+ is available**

```bash
node --version  # expect v20.x or v22.x
npm --version
```

If not installed: install Node 20 LTS first (via your platform package manager, e.g. `brew install node@20` on macOS).

- [ ] **Step 2: Scaffold Vite project**

```bash
cd /Users/arun/Devel/Github/pushnav
npm create vite@latest web -- --template react-ts
cd web
npm install
```

This creates `web/` with a working starter. Verify:

```bash
npm run dev
# Expect: VITE v5.x  ready in ... ms — http://localhost:5173/
# Open in browser: should show Vite + React starter.
# Ctrl-C
```

- [ ] **Step 3: Update `.gitignore`**

Append to `/Users/arun/Devel/Github/pushnav/.gitignore`:

```
# React front-end
web/node_modules/
web/dist/
web/.vite/
```

- [ ] **Step 4: Replace starter content**

Replace `web/src/App.tsx` with:

```tsx
export default function App() {
  return (
    <div className="min-h-screen flex items-center justify-center text-2xl">
      PushNav React UI scaffold
    </div>
  );
}
```

Replace `web/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Replace `web/src/index.css` with an empty file (Tailwind is added in Task 6).

- [ ] **Step 5: Add npm scripts for type-check**

In `web/package.json`, the Vite template already includes:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview"
}
```

No changes needed — verify these exist.

- [ ] **Step 6: Verify dev server still works**

```bash
cd web && npm run dev
# Open http://localhost:5173 — should show "PushNav React UI scaffold"
# Ctrl-C
```

- [ ] **Step 7: Commit**

```bash
git add web/ .gitignore
git commit -m "chore(web): scaffold Vite + React + TypeScript project

Initializes web/ with the Vite react-ts template. Replaces starter
landing with a placeholder. Adds web/node_modules and dist to .gitignore."
```

---

### Task 6: Add Tailwind CSS

**Files:**
- Create: `web/tailwind.config.ts`, `web/postcss.config.js`
- Modify: `web/src/index.css`, `web/package.json`

- [ ] **Step 1: Install Tailwind 3 and dependencies**

Tailwind 3 (not 4) is required for shadcn/ui compatibility:

```bash
cd web
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
```

This creates `tailwind.config.js` and `postcss.config.js`.

- [ ] **Step 2: Convert config to TypeScript**

Rename `tailwind.config.js` → `tailwind.config.ts` and replace contents:

```ts
import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {},
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 3: Add Tailwind directives to CSS**

Replace `web/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: Verify Tailwind works**

In `web/src/App.tsx`, the existing `className="min-h-screen flex items-center justify-center text-2xl"` should now produce a centered, large heading.

```bash
npm run dev
# Open http://localhost:5173 — should be visibly centered with large text
```

- [ ] **Step 5: Commit**

```bash
git add web/
git commit -m "chore(web): add Tailwind CSS"
```

---

### Task 7: Initialize shadcn/ui and add primitives

**Files:**
- Create: `web/components.json`, `web/src/lib/utils.ts`, `web/src/components/ui/*.tsx`
- Modify: `web/tailwind.config.ts`, `web/src/index.css`, `web/tsconfig.json`, `web/vite.config.ts`

- [ ] **Step 1: Configure path aliases in TypeScript and Vite**

shadcn requires `@/*` imports. Add to `web/tsconfig.json` `compilerOptions`:

```json
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

Install Vite path resolver and update `web/vite.config.ts`:

```bash
npm install -D @types/node
```

Replace `web/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    proxy: {
      "/ws":         { target: "ws://localhost:8080", ws: true },
      "/frame.mjpg": "http://localhost:8080",
      "/api":        "http://localhost:8080",
      "/sounds":     "http://localhost:8080",
      "/assets":     "http://localhost:8080",
    },
  },
});
```

- [ ] **Step 2: Run shadcn init**

```bash
cd web
npx shadcn@latest init
```

Answer prompts:
- Style: Default
- Base color: Slate
- CSS variables: Yes

This creates `components.json`, `src/lib/utils.ts`, and updates `tailwind.config.ts` + `src/index.css` with shadcn's CSS variables and theming.

- [ ] **Step 3: Add the primitives the UI needs**

```bash
npx shadcn@latest add button card slider switch dialog tabs badge separator scroll-area progress alert
```

Each component lands at `web/src/components/ui/<name>.tsx`. Inspect the directory:

```bash
ls web/src/components/ui/
# Expect: alert.tsx badge.tsx button.tsx card.tsx dialog.tsx progress.tsx
#         scroll-area.tsx separator.tsx slider.tsx switch.tsx tabs.tsx
```

- [ ] **Step 4: Smoke-test a primitive**

Replace `web/src/App.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <Card className="max-w-md mx-auto">
        <CardHeader>
          <CardTitle>PushNav</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

```bash
npm run dev
# Open http://localhost:5173 — should show a styled Card with three buttons
```

- [ ] **Step 5: Commit**

```bash
git add web/
git commit -m "chore(web): initialize shadcn/ui with primitives

Adds Button, Card, Slider, Switch, Dialog, Tabs, Badge, Separator,
ScrollArea, Progress, Alert. Configures @/* path alias and Vite proxy
for /ws, /frame.mjpg, /api, /sounds, /assets → localhost:8080."
```

---

### Task 8: Typed WebSocket state hook + API client

**Files:**
- Create: `web/src/lib/types.ts`, `web/src/lib/api.ts`, `web/src/hooks/useEngineState.ts`

- [ ] **Step 1: Define TypeScript types mirroring the `/ws` payload**

Create `web/src/lib/types.ts`:

```ts
// Mirror of webserver/_build_payload — keep in sync by hand.

export type EngineState =
  | "SETUP"
  | "SYNC"
  | "SYNC_CONFIRM"
  | "CALIBRATE"
  | "WARMING_UP"
  | "TRACKING"
  | "RECONNECTING"
  | "ERROR";

export interface PointingData {
  valid: boolean;
  ra_deg: number;
  dec_deg: number;
  roll_deg: number;
  matches: number;
  prob: number;
  solve_age_s: number | null;
}

export interface NavData {
  active: boolean;
  target_name: string | null;
  target_ra_deg: number;
  target_dec_deg: number;
  separation_deg: number | null;
  direction_text: string;
  in_fov: boolean;
  pixel_x: number | null;
  pixel_y: number | null;
  camera_angle_deg: number | null;
  edge_x: number | null;
  edge_y: number | null;
  edge_angle_deg: number | null;
}

export interface ControlDescriptor {
  id?: string;     // server uses "id"
  name?: string;   // some payloads use "name"
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  unit?: string;
}

export interface SyncCandidate {
  idx: number;
  name: string;
  ra_deg: number;
  dec_deg: number;
  magnitude: number;
}

export interface SyncBlock {
  in_progress: boolean;
  candidates: SyncCandidate[];
  selected_idx: number | null;
  error: string | null;
}

export interface ActivityLine {
  active: boolean;
  address: string | null;
  status?: unknown;
  object?: { name?: string; "localized-name"?: string } | null;
}

export interface CameraBlock {
  connected: boolean;
  all_centroids: number[][] | null;     // [[y, x], ...]
  matched_centroids: number[][] | null; // [[y, x], ...]
}

export interface EnginePayload {
  state: EngineState;
  failures: number;
  pointing: PointingData;
  nav: NavData | null;
  origin_x: number;
  origin_y: number;
  image_w: number;
  image_h: number;
  finder_rotation: number;
  fov_h_deg: number;
  controls: ControlDescriptor[];
  sync: SyncBlock;
  stellarium: ActivityLine;
  lx200: ActivityLine;
  webserver: { url: string | null };
  audio_enabled: boolean;
  camera: CameraBlock;
}
```

- [ ] **Step 2: Create the API client**

Create `web/src/lib/api.ts`:

```ts
async function post(path: string, body?: unknown): Promise<void> {
  const init: RequestInit = { method: "POST" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const resp = await fetch(path, init);
  if (resp.status >= 400) {
    throw new Error(`POST ${path} → ${resp.status}: ${await resp.text()}`);
  }
}

export const api = {
  wizardAdvance: () => post("/api/wizard/advance"),
  syncRetry: () => post("/api/sync/retry"),
  syncSelect: (idx: number) => post("/api/sync/select", { idx }),
  useCalibration: () => post("/api/calibration/use-previous"),
  setControl: (name: string, value: number) => post("/api/control", { name, value }),
  clearGoto: () => post("/api/goto/clear"),
  setSettings: (s: { audio_enabled?: boolean; hidpi?: boolean }) =>
    post("/api/settings", s),
};
```

- [ ] **Step 3: Create the WebSocket state hook**

Create `web/src/hooks/useEngineState.ts`:

```ts
import { useEffect, useRef, useState } from "react";
import type { EnginePayload } from "@/lib/types";

export function useEngineState(): EnginePayload | null {
  const [state, setState] = useState<EnginePayload | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | null = null;

    const connect = () => {
      // Vite dev: same-origin /ws is proxied to ws://localhost:8080/ws
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        try {
          setState(JSON.parse(ev.data) as EnginePayload);
        } catch (e) {
          console.error("Bad payload:", e);
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          retryTimer = window.setTimeout(connect, 1000);
        }
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []);

  return state;
}
```

- [ ] **Step 4: Smoke-test against the running engine**

In one terminal:

```bash
uv run python -m evf.main --dev --no-window
```

In another:

```bash
cd web && npm run dev
```

Replace `web/src/App.tsx` to wire up the hook:

```tsx
import { useEngineState } from "@/hooks/useEngineState";

export default function App() {
  const state = useEngineState();
  return (
    <div className="min-h-screen bg-background text-foreground p-8 font-mono">
      <h1 className="text-2xl mb-4">PushNav state</h1>
      <pre className="text-xs">{JSON.stringify(state, null, 2)}</pre>
    </div>
  );
}
```

Open `http://localhost:5173`. Expect: live JSON ticking 10× / second showing engine state, pointing, etc.

- [ ] **Step 5: Commit**

```bash
git add web/src/
git commit -m "feat(web): add typed WebSocket state hook and API client"
```

---

## Phase 3 — UI components (feature parity)

### Task 9: Live view with MJPEG + SVG overlay

**Files:**
- Create: `web/src/components/live-view/LiveView.tsx`, `web/src/components/live-view/StarOverlay.tsx`, `web/src/components/live-view/NavOverlay.tsx`

- [ ] **Step 1: Build `LiveView` component**

Create `web/src/components/live-view/LiveView.tsx`:

```tsx
import type { EnginePayload } from "@/lib/types";
import { StarOverlay } from "./StarOverlay";
import { NavOverlay } from "./NavOverlay";

interface Props {
  state: EnginePayload;
}

export function LiveView({ state }: Props) {
  const { image_w, image_h } = state;
  return (
    <div
      className="relative bg-black w-full"
      style={{ aspectRatio: `${image_w} / ${image_h}` }}
    >
      <img
        src="/frame.mjpg"
        alt="Live camera frame"
        className="absolute inset-0 w-full h-full object-cover"
      />
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${image_w} ${image_h}`}
        preserveAspectRatio="xMidYMid slice"
      >
        <StarOverlay state={state} />
        <NavOverlay state={state} />
      </svg>
    </div>
  );
}
```

- [ ] **Step 2: Build `StarOverlay` (centroids)**

Create `web/src/components/live-view/StarOverlay.tsx`:

```tsx
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function StarOverlay({ state }: Props) {
  const all = state.camera.all_centroids ?? [];
  const matched = state.camera.matched_centroids ?? [];
  const matchedKeys = new Set(matched.map(([y, x]) => `${y.toFixed(1)}:${x.toFixed(1)}`));
  return (
    <g>
      {all.map(([y, x], i) => {
        const isMatched = matchedKeys.has(`${y.toFixed(1)}:${x.toFixed(1)}`);
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={isMatched ? 8 : 6}
            fill="none"
            stroke={isMatched ? "#22d3ee" : "#64748b"}
            strokeWidth={isMatched ? 2 : 1}
          />
        );
      })}
    </g>
  );
}
```

- [ ] **Step 3: Build `NavOverlay` (target reticle + edge arrow)**

Create `web/src/components/live-view/NavOverlay.tsx`:

```tsx
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function NavOverlay({ state }: Props) {
  const nav = state.nav;
  if (!nav || !nav.active) return null;

  if (nav.in_fov && nav.pixel_x !== null && nav.pixel_y !== null) {
    return (
      <g>
        <circle cx={nav.pixel_x} cy={nav.pixel_y} r={20} fill="none" stroke="#fde047" strokeWidth={2} />
        <line x1={nav.pixel_x - 28} y1={nav.pixel_y} x2={nav.pixel_x - 14} y2={nav.pixel_y} stroke="#fde047" strokeWidth={2} />
        <line x1={nav.pixel_x + 14} y1={nav.pixel_y} x2={nav.pixel_x + 28} y2={nav.pixel_y} stroke="#fde047" strokeWidth={2} />
        <line x1={nav.pixel_x} y1={nav.pixel_y - 28} x2={nav.pixel_x} y2={nav.pixel_y - 14} stroke="#fde047" strokeWidth={2} />
        <line x1={nav.pixel_x} y1={nav.pixel_y + 14} x2={nav.pixel_x} y2={nav.pixel_y + 28} stroke="#fde047" strokeWidth={2} />
      </g>
    );
  }

  if (nav.edge_x !== null && nav.edge_y !== null && nav.edge_angle_deg !== null) {
    return (
      <g transform={`translate(${nav.edge_x}, ${nav.edge_y}) rotate(${nav.edge_angle_deg})`}>
        <polygon points="0,-22 -14,10 14,10" fill="#fde047" />
      </g>
    );
  }

  return null;
}
```

- [ ] **Step 4: Wire into App for visual check**

Replace `web/src/App.tsx`:

```tsx
import { useEngineState } from "@/hooks/useEngineState";
import { LiveView } from "@/components/live-view/LiveView";

export default function App() {
  const state = useEngineState();
  if (!state) return <div className="p-8">Connecting...</div>;
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-4xl mx-auto p-4">
        <LiveView state={state} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Manual visual check**

Run engine + dev server:

```bash
# Terminal 1
uv run python -m evf.main --dev --no-window

# Terminal 2
cd web && npm run dev
```

Open `http://localhost:5173`. Expect:
- Live frame visible (or black if no camera).
- Once tracking, faint circles at every detected star, brighter cyan circles at matched stars.
- If a GOTO is sent (test via Stellarium or `engine.goto_target.set(ra, dec)`), see reticle when in-FOV or edge arrow when out.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/live-view/ web/src/App.tsx
git commit -m "feat(web): add LiveView with MJPEG image and SVG overlays"
```

---

### Task 10: Camera control sliders

**Files:**
- Create: `web/src/components/controls/CameraControls.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Build `CameraControls` component**

Create `web/src/components/controls/CameraControls.tsx`:

```tsx
import { useState, useEffect } from "react";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ControlDescriptor } from "@/lib/types";

interface Props {
  controls: ControlDescriptor[];
}

export function CameraControls({ controls }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Camera</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {controls.map((c) => (
          <ControlRow key={c.id ?? c.name} control={c} />
        ))}
      </CardContent>
    </Card>
  );
}

function ControlRow({ control }: { control: ControlDescriptor }) {
  const id = control.id ?? control.name ?? "";
  const [local, setLocal] = useState(control.value);

  // Reflect server-side updates
  useEffect(() => { setLocal(control.value); }, [control.value]);

  const commit = (v: number) => {
    setLocal(v);
    api.setControl(id, v).catch((e) => console.error(e));
  };

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{control.label}</span>
        <span className="text-muted-foreground">
          {local}{control.unit ? ` ${control.unit}` : ""}
        </span>
      </div>
      <Slider
        min={control.min}
        max={control.max}
        step={control.step ?? 1}
        value={[local]}
        onValueChange={([v]) => setLocal(v)}
        onValueCommit={([v]) => commit(v)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Add to App**

```tsx
import { CameraControls } from "@/components/controls/CameraControls";

// inside <App>
<div className="grid md:grid-cols-3 gap-4 mt-4">
  <div className="md:col-span-2"><LiveView state={state} /></div>
  <CameraControls controls={state.controls} />
</div>
```

- [ ] **Step 3: Manual test**

Run dev environment. Drag exposure / gain sliders. Expect: camera frame visibly changes brightness when sliders are committed. Engine logs show `set_control` calls.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/controls/ web/src/App.tsx
git commit -m "feat(web): add camera control sliders"
```

---

### Task 11: Wizard component (state → step UI)

**Files:**
- Create: `web/src/components/wizard/Wizard.tsx`, `web/src/components/wizard/SyncStep.tsx`, `web/src/components/wizard/SyncConfirmStep.tsx`, `web/src/components/wizard/CalibrateStep.tsx`, `web/src/components/wizard/TrackingStep.tsx`, `web/src/components/wizard/SetupStep.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Build the dispatcher**

Create `web/src/components/wizard/Wizard.tsx`:

```tsx
import type { EnginePayload } from "@/lib/types";
import { SetupStep } from "./SetupStep";
import { SyncStep } from "./SyncStep";
import { SyncConfirmStep } from "./SyncConfirmStep";
import { CalibrateStep } from "./CalibrateStep";
import { TrackingStep } from "./TrackingStep";

interface Props {
  state: EnginePayload;
}

export function Wizard({ state }: Props) {
  switch (state.state) {
    case "SETUP":        return <SetupStep state={state} />;
    case "SYNC":         return <SyncStep state={state} />;
    case "SYNC_CONFIRM": return <SyncConfirmStep state={state} />;
    case "CALIBRATE":    return <CalibrateStep state={state} />;
    case "WARMING_UP":
    case "TRACKING":     return <TrackingStep state={state} />;
    case "RECONNECTING": return <div className="p-4">Reconnecting to camera…</div>;
    case "ERROR":        return <div className="p-4 text-destructive">Error — restart required</div>;
    default:             return null;
  }
}
```

- [ ] **Step 2: Build each step**

Create `web/src/components/wizard/SetupStep.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function SetupStep({ state: _ }: { state: EnginePayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 1 — Setup</CardTitle>
        <CardDescription>
          Confirm the camera is in focus and stars are visible, then begin sync.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex gap-2">
        <Button onClick={() => api.wizardAdvance()}>Begin Sync</Button>
        <Button variant="outline" onClick={() => api.useCalibration()}>
          Use previous calibration
        </Button>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/wizard/SyncStep.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function SyncStep({ state }: { state: EnginePayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2 — Sync</CardTitle>
        <CardDescription>
          Center a known bright star in the eyepiece and tap "Solve frame".
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {state.sync.error && (
          <Alert variant="destructive">
            <AlertDescription>{state.sync.error}</AlertDescription>
          </Alert>
        )}
        <Button
          disabled={state.sync.in_progress}
          onClick={() => api.wizardAdvance()}
        >
          {state.sync.in_progress ? "Solving…" : "Solve frame"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/wizard/SyncConfirmStep.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function SyncConfirmStep({ state }: { state: EnginePayload }) {
  const candidates = state.sync.candidates;
  const selectedIdx = state.sync.selected_idx;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2b — Confirm sync star</CardTitle>
        <CardDescription>
          Tap the star you actually centered. The brightest auto-selected pick is highlighted.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {candidates.map((c) => (
            <button
              key={c.idx}
              onClick={() => api.syncSelect(c.idx)}
              className={`text-left p-2 border rounded transition ${
                c.idx === selectedIdx ? "border-primary bg-primary/10" : "border-muted"
              }`}
            >
              <div className="font-medium">{c.name}</div>
              <Badge variant="secondary">mag {c.magnitude.toFixed(1)}</Badge>
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => api.wizardAdvance()}>Confirm</Button>
          <Button variant="outline" onClick={() => api.syncRetry()}>Re-solve</Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/wizard/CalibrateStep.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function CalibrateStep({ state: _ }: { state: EnginePayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 3 — Calibrate</CardTitle>
        <CardDescription>
          Move the telescope at least 0.5° in any direction and hold steady.
          Calibration completes automatically once movement stabilises.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" onClick={() => api.wizardAdvance()}>
          Skip calibration
        </Button>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/wizard/TrackingStep.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function TrackingStep({ state }: { state: EnginePayload }) {
  const p = state.pointing;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Tracking</CardTitle>
          <Badge variant={p.valid ? "default" : "destructive"}>
            {p.valid ? "LOCK" : "LOST"}
          </Badge>
        </div>
        <CardDescription>
          {p.valid
            ? `RA ${p.ra_deg.toFixed(2)}° / Dec ${p.dec_deg.toFixed(2)}° / age ${p.solve_age_s}s`
            : "Acquiring stars…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {state.nav?.active && (
          <div>
            Target: <strong>{state.nav.target_name ?? "—"}</strong> · {state.nav.direction_text} ·{" "}
            {state.nav.separation_deg !== null ? `${state.nav.separation_deg.toFixed(2)}°` : "—"}
            <Button variant="ghost" size="sm" onClick={() => api.clearGoto()} className="ml-2">
              Clear
            </Button>
          </div>
        )}
        <Button variant="outline" onClick={() => api.wizardAdvance()}>
          Stop tracking
        </Button>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Vitest setup + write a wizard component test**

```bash
cd web
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

Add to `web/package.json` `scripts`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

Add to `web/vite.config.ts` (top-level, not inside the default export):

```ts
/// <reference types="vitest" />
```

And inside `defineConfig({...})`:

```ts
test: {
  environment: "jsdom",
  globals: true,
  setupFiles: ["./src/test-setup.ts"],
},
```

Create `web/src/test-setup.ts`:

```ts
import "@testing-library/jest-dom";
```

Create `web/src/components/wizard/Wizard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Wizard } from "./Wizard";
import type { EnginePayload } from "@/lib/types";

const base: EnginePayload = {
  state: "SETUP", failures: 0,
  pointing: { valid: false, ra_deg: 0, dec_deg: 0, roll_deg: 0, matches: 0, prob: 1, solve_age_s: null },
  nav: null,
  origin_x: 640, origin_y: 360, image_w: 1280, image_h: 720,
  finder_rotation: 0, fov_h_deg: 8.86,
  controls: [], sync: { in_progress: false, candidates: [], selected_idx: null, error: null },
  stellarium: { active: false, address: null }, lx200: { active: false, address: null },
  webserver: { url: null }, audio_enabled: true,
  camera: { connected: false, all_centroids: null, matched_centroids: null },
};

describe("Wizard", () => {
  it("renders the setup step in SETUP state", () => {
    render(<Wizard state={{ ...base, state: "SETUP" }} />);
    expect(screen.getByRole("button", { name: /begin sync/i })).toBeInTheDocument();
  });

  it("renders the sync step in SYNC state", () => {
    render(<Wizard state={{ ...base, state: "SYNC" }} />);
    expect(screen.getByRole("button", { name: /solve frame/i })).toBeInTheDocument();
  });

  it("renders LOCK badge when tracking is valid", () => {
    const s = { ...base, state: "TRACKING" as const,
      pointing: { ...base.pointing, valid: true, solve_age_s: 0.2 } };
    render(<Wizard state={s} />);
    expect(screen.getByText(/LOCK/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd web && npm test
```

Expected: 3 passing.

- [ ] **Step 5: Wire into App**

Replace `web/src/App.tsx`:

```tsx
import { useEngineState } from "@/hooks/useEngineState";
import { LiveView } from "@/components/live-view/LiveView";
import { CameraControls } from "@/components/controls/CameraControls";
import { Wizard } from "@/components/wizard/Wizard";

export default function App() {
  const state = useEngineState();
  if (!state) return <div className="p-8">Connecting...</div>;
  return (
    <div className="min-h-screen bg-background text-foreground p-4">
      <div className="grid md:grid-cols-3 gap-4 max-w-7xl mx-auto">
        <div className="md:col-span-2 space-y-4">
          <LiveView state={state} />
          <Wizard state={state} />
        </div>
        <div className="space-y-4">
          <CameraControls controls={state.controls} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Manual end-to-end test**

Run engine + dev server. Walk through the wizard against the live rig (or mock camera): SETUP → SYNC → SYNC_CONFIRM → CALIBRATE → TRACKING. Verify each step renders the right UI and buttons advance state correctly.

- [ ] **Step 7: Commit**

```bash
git add web/
git commit -m "feat(web): add wizard component covering all engine states

Step UIs for SETUP/SYNC/SYNC_CONFIRM/CALIBRATE/TRACKING dispatched off
state.state. Vitest + RTL set up; basic state-routing tests."
```

---

### Task 12: Settings panel

**Files:**
- Create: `web/src/components/settings/Settings.tsx`, `web/src/components/settings/QrCode.tsx`
- Modify: `web/src/App.tsx`, `web/package.json`

- [ ] **Step 1: Install QR library**

```bash
cd web && npm install qrcode.react
```

- [ ] **Step 2: Build Settings component**

Create `web/src/components/settings/Settings.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function Settings({ state }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Row label="Audio feedback">
          <Switch
            checked={state.audio_enabled}
            onCheckedChange={(v) => api.setSettings({ audio_enabled: v })}
          />
        </Row>
        <Separator />
        <div>
          <div className="text-sm font-medium mb-1">Phone web URL</div>
          {state.webserver.url ? (
            <div className="flex items-center gap-3">
              <QRCodeSVG value={state.webserver.url} size={96} />
              <code className="text-xs break-all">{state.webserver.url}</code>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">No LAN IP detected</div>
          )}
        </div>
        <Separator />
        <Row label="Stellarium">
          <code className="text-xs">{state.stellarium.address ?? "off"}</code>
        </Row>
        <Row label="LX200 (SkySafari)">
          <code className="text-xs">{state.lx200.address ?? "off"}</code>
        </Row>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Place in App via Tabs**

Update `web/src/App.tsx` right column to use Tabs:

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Settings } from "@/components/settings/Settings";

// inside the right column:
<Tabs defaultValue="camera">
  <TabsList>
    <TabsTrigger value="camera">Camera</TabsTrigger>
    <TabsTrigger value="settings">Settings</TabsTrigger>
  </TabsList>
  <TabsContent value="camera"><CameraControls controls={state.controls} /></TabsContent>
  <TabsContent value="settings"><Settings state={state} /></TabsContent>
</Tabs>
```

- [ ] **Step 4: Manual test**

Run dev environment. Open Settings tab. Toggle audio — engine logs should show audio enable/disable. Verify QR code renders and scannable from a phone.

- [ ] **Step 5: Commit**

```bash
git add web/
git commit -m "feat(web): add Settings panel with audio toggle, QR code, addresses"
```

---

### Task 13: Splash + camera disconnect dialog

**Files:**
- Create: `web/src/components/splash/Splash.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Build Splash overlay**

Create `web/src/components/splash/Splash.tsx`:

```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { EnginePayload } from "@/lib/types";

interface Props { state: EnginePayload | null }

export function Splash({ state }: Props) {
  if (state === null) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader><DialogTitle>Connecting…</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Waiting for engine.</p>
        </DialogContent>
      </Dialog>
    );
  }
  if (!state.camera.connected) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader><DialogTitle>Camera not found</DialogTitle></DialogHeader>
          <p className="text-sm">Plug in the USB camera and restart PushNav.</p>
        </DialogContent>
      </Dialog>
    );
  }
  return null;
}
```

- [ ] **Step 2: Render at App root**

```tsx
import { Splash } from "@/components/splash/Splash";

// inside <App>, render alongside the grid:
<Splash state={state} />
```

- [ ] **Step 3: Manual test**

Run dev server with engine **not** running — expect "Connecting…" dialog. Start engine — expect dialog to disappear once /ws is connected and camera is reported connected.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/splash/ web/src/App.tsx
git commit -m "feat(web): add splash + camera-not-found dialogs"
```

---

## Phase 4 — pywebview integration

### Task 14: Add pywebview dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `pywebview` to dependencies**

In `pyproject.toml`, add to `[project] dependencies`:

```toml
"pywebview>=5.0",
```

(Keep `dearpygui` for now — DPG and React run side-by-side until cutover in Task 17.)

- [ ] **Step 2: Sync**

```bash
uv sync
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "import webview; print(webview.__version__)"
# Expect: 5.x output
```

- [ ] **Step 4: Linux-specific note**

On Linux, pywebview needs `gi` and WebKit2 GTK bindings. If `import webview` fails on Linux:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1
# or for older systems:
sudo apt install python3-gi gir1.2-webkit2-4.0
```

This is a system-package dependency; document in README install instructions. **No commit yet — it's just a verification step.**

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pywebview>=5.0 dependency"
```

---

### Task 15: Add `--react` mode to `main.py`

**Files:**
- Modify: `python/evf/main.py`

- [ ] **Step 1: Add the flag**

At the top of `main()`, near the existing flag parsing:

```python
react_mode = "--react" in sys.argv
```

- [ ] **Step 2: Branch into pywebview path**

After the engine is created and configured (after the existing Windows scale detection block), add:

```python
if react_mode:
    import webview

    # Start the engine + servers headless (no DPG)
    engine.startup_logging()
    engine.startup_solver()
    engine.startup_stellarium()
    engine.startup_lx200()
    engine.startup_webserver()
    engine.startup_camera()
    if engine.camera_connected:
        engine.startup_solver_thread()

    # In dev, point the webview at Vite (HMR). In prod, point at aiohttp.
    target_url = "http://localhost:5173" if dev_mode else "http://localhost:8080"
    title = f"PushNav {engine.app_version}"

    webview.create_window(
        title,
        target_url,
        width=int(_VP_WIDTH * vp_scale) + _CHROME_BUFFER,
        height=int(_VP_HEIGHT * vp_scale),
        resizable=True,
    )
    webview.start()  # blocks until window closed

    engine.shutdown()
    return
```

Place this immediately before the existing `dpg.create_context()` line, so DPG only runs when `--react` is *not* set.

- [ ] **Step 3: Manual smoke test**

```bash
# Terminal 1
cd web && npm run dev

# Terminal 2
uv run python -m evf.main --dev --react
```

Expect: a real native window opens (NOT a browser tab) showing the React UI from Vite. Close window → engine shuts down cleanly.

```bash
# Production-shape test (skip Vite, use aiohttp-served build)
cd web && npm run build       # → web/dist/
# (Production serving from web/dist/ requires Task 18 — defer for now.)
```

- [ ] **Step 4: Commit**

```bash
git add python/evf/main.py
git commit -m "feat(main): add --react mode launching React UI in pywebview window

Engine + aiohttp run as today; pywebview hosts the React app from Vite
(in --dev) or from the aiohttp-served build (in prod). DPG path remains
the default until cutover."
```

---

### Task 16: Serve `web/dist/` from aiohttp in prod

**Files:**
- Modify: `python/evf/webserver/server.py`, `python/evf/paths.py`

- [ ] **Step 1: Add `web_dist_dir()` to paths**

In `python/evf/paths.py`, append:

```python
def web_dist_dir() -> Path:
    """Path to the built React app (web/dist/) — present only in release or after `npm run build`."""
    if _BUNDLE_MODE:
        return _RESOURCES / "web_dist"
    if _LINUX_RELEASE or _WINDOWS_RELEASE:
        return _RELEASE_ROOT / "data" / "web_dist"
    return _REPO_ROOT / "web" / "dist"
```

- [ ] **Step 2: Replace `_handle_index` with static-files serving**

In `python/evf/webserver/server.py`, replace:

```python
async def _handle_index(self, request: web.Request) -> web.FileResponse:
    return web.FileResponse(web_dir() / "index.html")
```

with:

```python
async def _handle_index(self, request: web.Request) -> web.FileResponse:
    """Serve the React app shell. Falls back to legacy data/web/index.html if dist missing."""
    from evf.paths import web_dist_dir
    dist = web_dist_dir()
    if (dist / "index.html").exists():
        return web.FileResponse(dist / "index.html")
    return web.FileResponse(web_dir() / "index.html")
```

And in `_serve()`, register the dist assets *before* the legacy `/assets`:

```python
from evf.paths import web_dist_dir
dist = web_dist_dir()
if dist.exists():
    app.router.add_static("/static", dist, name="react_static")
```

- [ ] **Step 3: Update React build to emit assets under `/static/`**

In `web/vite.config.ts`, set the base path:

```ts
export default defineConfig({
  // ...
  base: "/static/",
  build: { outDir: "dist", assetsDir: "" },
});
```

(Keep dev `server` block as-is — `base` only affects build output paths.)

- [ ] **Step 4: Verify production-shape works**

```bash
cd web && npm run build
uv run python -m evf.main --react   # NO --dev — hits aiohttp-served build
```

Expect: pywebview window opens at localhost:8080, shows the React UI rendered from `web/dist/`.

- [ ] **Step 5: Commit**

```bash
git add python/evf/webserver/server.py python/evf/paths.py web/vite.config.ts
git commit -m "feat(webserver): serve web/dist/ React build at / in prod

Vite's base is set to /static/ so JS/CSS load from /static/*. The legacy
data/web/index.html stays as a fallback for now (removed in cutover)."
```

---

## Phase 5 — Cutover

### Task 17: Remove DPG and dead code

**Files:**
- Delete: `python/evf/ui/window.py`, `python/evf/ui/__init__.py`, `python/evf/ui/`, `data/web/index.html`
- Move: `data/web/inapp-title.png` → `web/public/inapp-title.png`, `data/web/logo.png` → `web/public/logo.png`
- Modify: `pyproject.toml`, `python/evf/main.py`

- [ ] **Step 1: Confirm `--react` mode is feature-complete**

Run end-to-end on the live rig:

```bash
cd web && npm run build
uv run python -m evf.main --react
```

Walk through SETUP → SYNC → SYNC_CONFIRM → CALIBRATE → TRACKING. Verify camera controls, settings, GOTO from Stellarium, audio, QR code. **Do not proceed if anything is broken.**

- [ ] **Step 2: Move static assets**

```bash
mkdir -p web/public
git mv data/web/inapp-title.png web/public/inapp-title.png
git mv data/web/logo.png web/public/logo.png
```

- [ ] **Step 3: Remove DPG and legacy web UI**

```bash
git rm -r python/evf/ui
git rm data/web/index.html
rmdir data/web 2>/dev/null || true   # remove dir if empty
```

- [ ] **Step 4: Drop `dearpygui` from dependencies**

Edit `pyproject.toml`:

```toml
dependencies = [
    "Pillow",
    "numpy",
    "scipy",
    "tetra3",
    "playsound3",
    "aiohttp",
    "qrcode[pil]",
    "pyerfa>=2.0.0",
    "pywebview>=5.0",
]
```

```bash
uv sync
```

- [ ] **Step 5: Simplify `main.py`**

Replace `python/evf/main.py` body with the React-only path. The Windows DPI helpers stay (relevant to webview window size); the DPG-specific code goes:

```python
def main() -> None:
    dev_mode = "--dev" in sys.argv
    no_window = "--no-window" in sys.argv

    engine = Engine()

    # Windows display scale tracking (unchanged) — relevant to window size
    if sys.platform == "win32":
        current_scale = _windows_primary_monitor_scale()
        if current_scale != engine.config.hidpi_last_scale:
            should_hidpi = current_scale >= 150
            if engine.config.hidpi != should_hidpi:
                engine.config.hidpi = should_hidpi
            engine.config.hidpi_last_scale = current_scale

    vp_scale = 2 if engine.config.hidpi else 1

    engine.startup_logging()
    engine.startup_solver()
    engine.startup_stellarium()
    engine.startup_lx200()
    engine.startup_webserver()
    engine.startup_camera()
    if engine.camera_connected:
        engine.startup_solver_thread()

    if no_window:
        logger.info("Running headless (--no-window). Press Ctrl-C to exit.")
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        stop.wait()
        engine.shutdown()
        return

    import webview
    target_url = "http://localhost:5173" if dev_mode else "http://localhost:8080"
    title = f"PushNav {engine.app_version}"
    webview.create_window(
        title,
        target_url,
        width=int(_VP_WIDTH * vp_scale) + _CHROME_BUFFER,
        height=int(_VP_HEIGHT * vp_scale),
        resizable=True,
    )
    webview.start()

    engine.shutdown()
```

You can also drop the `_windows_disable_maximize_button` function — pywebview windows handle their own chrome. Drop the `import dearpygui.dearpygui as dpg` and `from evf.ui.window import UI` imports.

- [ ] **Step 6: Verify everything still runs**

```bash
cd web && npm run build
uv run python -m evf.main
```

Expect: pywebview window opens with the React UI. No DPG ever loaded.

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expect: all tests pass (none depend on DPG, but verify no surprise import).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: remove DearPyGui — React UI is now the only frontend

Deletes python/evf/ui/window.py (1896 lines), data/web/index.html, and
the dearpygui dependency. Moves logo + title PNG into web/public/.
main.py reduced to engine bootstrap + pywebview window."
```

---

### Task 18: Update build scripts to bundle React build

**Files:**
- Modify: `scripts/build_mac.sh`, `scripts/build_linux.sh`, `scripts/build_windows.bat`

- [ ] **Step 1: Update `scripts/build_mac.sh`**

After the camera build phase, before invoking Nuitka, add a phase that builds the React app and includes it as a Nuitka data dir:

```bash
echo "==> Building React UI"
(cd "$REPO_ROOT/web" && npm ci && npm run build)
if [ ! -f "$REPO_ROOT/web/dist/index.html" ]; then
    echo "ERROR: React build did not produce web/dist/index.html"
    exit 1
fi
```

Locate the existing Nuitka invocation and add a `--include-data-dir` flag:

```bash
--include-data-dir="$REPO_ROOT/web/dist=web_dist" \
```

(Adjust the existing `\` line continuations.)

The mac path already uses `_RESOURCES / "web_dist"` per the `web_dist_dir()` function — verify the Nuitka data-dir landing matches.

- [ ] **Step 2: Update `scripts/build_linux.sh`** with the same React build phase + `--include-data-dir="$REPO_ROOT/web/dist=data/web_dist"`.

- [ ] **Step 3: Update `scripts/build_windows.bat`** equivalently:

```bat
echo ==^> Building React UI
pushd "%REPO_ROOT%\web"
call npm ci
call npm run build
popd
if not exist "%REPO_ROOT%\web\dist\index.html" (
    echo ERROR: React build did not produce web\dist\index.html
    exit /b 1
)
```

And add to the Nuitka invocation: `--include-data-dir="%REPO_ROOT%\web\dist=data\web_dist"`.

- [ ] **Step 4: Test build on at least one platform**

On macOS:

```bash
./scripts/build_mac.sh
open build/PushNav.app
```

Expect: app launches, pywebview window shows React UI, all features work end-to-end.

- [ ] **Step 5: Commit**

```bash
git add scripts/
git commit -m "build: add React UI build step to platform build scripts

Each script runs 'npm ci && npm run build' before Nuitka, then includes
web/dist/ as a Nuitka data dir mapped to web_dist/ inside the bundle."
```

---

### Task 19: Update docs and CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`, `specs/start/SPEC_ARCHITECTURE.md`, `docs/install.md` (if it documents UI framework)

- [ ] **Step 1: Update `CLAUDE.md`**

Replace the DearPyGui mention in the project overview with React/pywebview language. In the Project Layout section, replace the `python/evf/ui/` line and add `web/`:

```
python/evf/                     # main Python package (engine + servers)
web/                            # React + Vite + ShadCN front-end
  src/                          # React components, hooks, lib
  dist/                         # build output (gitignored; emitted by `npm run build`)
```

Update Build & Run:

```bash
uv sync                          # install Python deps from lockfile
(cd web && npm install)          # install Node deps
(cd web && npm run dev) &        # Vite HMR on :5173
uv run python -m evf.main --dev  # launch app (pywebview window points at :5173)
```

Update Key Dependencies — replace DearPyGui line with:

```
- **pywebview** — wraps the OS webview (WebKit/WebView2/GTK) for the desktop window
- **React + Vite + Tailwind + shadcn/ui** — front-end stack (web/)
```

- [ ] **Step 2: Update `specs/start/SPEC_ARCHITECTURE.md`**

Section 2 ("System Overview"): replace the DearPyGui block with a pywebview block. Section 4.1 ("UI Thread"): rewrite the live-texture details to describe MJPEG `<img>` + SVG overlays. Section 4.5 ("Web Server Thread"): note the additions (`/frame.mjpg`, `/api/*`, extended `/ws` schema).

- [ ] **Step 3: Run docs build to catch breakage**

```bash
uv run --group docs mkdocs build --strict
```

Expect: clean build.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md specs/ docs/
git commit -m "docs: update architecture and CLAUDE.md for React UI"
```

---

## Self-review

**Spec coverage:**

| Spec section | Tasks |
|---|---|
| §2 Architecture | Tasks 1–4 (engine API), 5–7 (scaffold), 14–16 (pywebview) |
| §3 Repo Layout | Tasks 5 (web/), 17 (delete ui/, data/web/) |
| §4 Dev Workflow | Task 4 (--no-window), Task 7 (Vite proxy) |
| §5 New Engine API Surface | Tasks 1 (MJPEG), 2 (/ws fields), 3 (POST /api/*) |
| §5.2 Star/nav SVG overlay | Task 9 |
| §5.3 MJPEG endpoint | Task 1 |
| §6 Production Packaging | Tasks 16, 18 |
| §6.1 pywebview platform notes | Task 14 (Linux deps callout) |
| §7 Migration Strategy | Tasks 5–13 build alongside; Task 17 cuts over |
| §8 Testing Strategy | Task 1 (mjpeg test), 2 (payload test), 3 (api test), 11 (component tests) |
| §9 Risk: Linux pywebview | Task 14 step 4 |
| §11 Acceptance Criteria | All 5 items covered by Tasks 9, 10, 11, 12, 13, 17, 18 |

No spec section is uncovered.

**Placeholder scan:** No `TBD`, `TODO`, "implement later", or "similar to Task N" — every step has actual code or commands.

**Type/method consistency:**

- `EngineActions` Protocol (Task 3) defines `step_advance`, `sync_retry`, `set_sync_selected(idx)`, `use_previous_calibration`, `set_control(name, value)`, `clear_goto_target`, `set_audio_enabled(enabled)`, `set_hidpi(enabled)`. Engine already has all of these except `set_audio_enabled` and `set_hidpi`, which Task 3 step 5 adds.
- API client `api` object methods (Task 8) — `wizardAdvance`, `syncRetry`, `syncSelect`, `useCalibration`, `setControl`, `clearGoto`, `setSettings` — match the endpoint paths in Task 3.
- TypeScript `EnginePayload` (Task 8) field names match the keys produced by `_build_payload` in Task 2. `controls` uses `id` per the existing `client.controls` shape; `ControlDescriptor` has `id?` and `name?` optional to be tolerant.
- `frame_buffer.get()` returns `(jpeg, ts, frame_id)` — used in Task 1 step 4 and Task 2 step 4. Verified against `python/evf/engine/frame_buffer.py`.
- `web_dist_dir()` (Task 16) is referenced in Task 18 step 1 — paths align.
- Vite `base: "/static/"` (Task 16) matches the aiohttp `add_static("/static", dist)` route in the same task.

All consistent.

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-react-ui-pivot.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
