# ODrive GUI — agent guide

A small [NiceGUI](https://nicegui.io) web app to tune and debug [ODrive](https://odriverobotics.com) motor controllers.
It discovers ODrives on the USB bus and renders one live control panel per device.

## Layout

| Path | What |
|---|---|
| `src/main.py` | Entry point: USB discovery loop + the page. `python src/main.py`. |
| `src/controls.py` | The per-device control panel — `controls(odrv)`. All the UI lives here. |
| `src/theme.py` | Shared colour scheme, default props + dark mode (`apply_theme()`), used by the app and the mock runner. |
| `tools/mock_odrive.py` | A faithful in-memory fake ODrive **+ a stub of the `odrive` package** (incl. its discovery API). Lets the UI run, be screenshotted and tested with **no hardware attached**. |
| `tools/run_mock.py` | `python tools/run_mock.py [port]` — runs the real `main.py` with one mock device plugged in. |
| `tests/` | pytest tests driving the mock through NiceGUI's `User` fixture: the panel (`test_render.py`) and the real `main.py` incl. hot-plugging (`test_main.py`). |

## Run it

```bash
uv sync

uv run python src/main.py            # needs a real ODrive on USB
uv run python tools/run_mock.py      # no hardware — opens on :8113
```

## Test / lint / type-check (the CI gates)

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
```

Note: `pytest` runs against the odrive **stub** (`tests/conftest.py`), so a green suite says nothing about the real `odrive` import.
CI's separate `boot` job is what verifies `src/main.py` actually starts against the locked dependency set, and its `docker` job that the published image does too.

## How the device object works (important)

`controls(odrv)` takes a **live `fibre` remote object**, so it is dynamically typed (`Any`).
Every attribute it reads (`odrv.axis0.motor.current_control.Iq_measured`, `odrv.axis0.controller.config.pos_gain`, …) mirrors the ODrive 0.5.x/0.6.x object tree.
Every property read is a blocking USB round-trip, so after the panel is built all device traffic goes through the single `_usb` worker in `controls.py` (`_Mirror` for bound values, `_on_usb` for timer reads, `_send` for writes and commands) — never read or write the device on the event loop, and keep timers lean.
When you change the UI, mirror the same attribute path in `tools/mock_odrive.py` so the hardware-free tests keep covering it.

## Page structure (NiceGUI 3.x)

Never create UI at module scope in `main.py`.
With NiceGUI 3.x that switches on "script mode", where the file is re-executed per page request and elements built by the startup loop belong to a client no browser sees.
`main.py` therefore keeps a plain `devices` registry, maintained by the discovery loop, and renders per client from it in `@ui.page('/')` via a `ui.refreshable` that the loop refreshes on every hot-plug event.

## Hardware safety (if you connect a real ODrive)

This GUI can command motion (the torque/velocity/position buttons) and switch an axis into closed-loop control.
On a clone board **without hardware overcurrent protection**, software `current_lim` is the only real-time motor protection.
Do not energize an unattended motor; never run open-loop for long.
Treat config display and telemetry as the safe read-only baseline.
