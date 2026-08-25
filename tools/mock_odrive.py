"""A faithful in-memory fake of an ODrive device + a stub of the ``odrive`` package.

This lets the GUI run (and be screenshotted / tested) with **no hardware attached**.
It mirrors exactly the attribute graph that ``src/controls.py`` reads and writes.

Two entry points:

* ``install_odrive_stub()`` -- registers fake ``odrive``, ``odrive.pyfibre.fibre``
  and ``odrive.utils`` modules in ``sys.modules`` so ``import odrive`` /
  ``from odrive.utils import dump_errors`` succeed without the real package.
* ``make_mock_odrive(serial=...)`` -- returns one fake device whose config
  objects accept ``setattr`` (so NiceGUI two-way bindings work) and whose
  telemetry fields animate over time (so plots/labels look alive in a capture).
"""

from __future__ import annotations

import concurrent.futures
import math
import sys
import time
import types

_T0 = time.time()


def _wave(period: float, amp: float, offset: float = 0.0) -> float:
    return offset + amp * math.sin(2 * math.pi * (time.time() - _T0) / period)


class _Config:
    """A plain settable namespace -- NiceGUI bindings get/set attributes here."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _CurrentControl:
    Iq_setpoint = 0.4
    Id_setpoint = 0.0

    @property
    def Iq_measured(self) -> float:
        return _wave(2.0, 0.05, 0.42)

    @property
    def Id_measured(self) -> float:
        return _wave(2.0, 0.03, 0.0)

    @property
    def v_current_control_integral_q(self) -> float:
        return _wave(3.0, 0.2, 1.1)


class _Thermistor:
    """The FET thermistor, mirroring ``odrv.axisN.motor.fet_thermistor``.

    Exposes only ``.temperature`` — deliberately its own class rather than aliasing the
    axis, so the mock's object graph is shape-faithful. ``controls.py`` uses ``hasattr``
    feature-detection; a stray path like ``axis.current_control`` or ``axis.temperature``
    must therefore fail here (as on real hardware) instead of silently resolving.
    """

    @property
    def temperature(self) -> float:
        return _wave(20.0, 4.0, 32.0)


class _MockAxis:
    def __init__(self, calibrated: bool = True, control_mode: int = 2) -> None:
        self.error = 0
        self.requested_state = 1
        self.current_state = 1
        self.motor = types.SimpleNamespace(
            is_calibrated=calibrated,
            current_control=_CurrentControl(),  # lives on the motor only, as on hardware
            config=_Config(current_lim=10.0, current_control_bandwidth=1000.0, torque_lim=float('inf'), requested_current_range=60.0),
            fet_thermistor=_Thermistor(),
        )
        self.controller = types.SimpleNamespace(
            input_torque=0.0,
            input_vel=0.0,
            input_pos=0.0,
            config=_Config(
                control_mode=control_mode,
                input_mode=1,
                pos_gain=20.0,
                vel_gain=0.16,
                vel_integrator_gain=0.32,
                vel_differentiator_gain=0.0,
                vel_limit=10.0,
                inertia=0.0,
                vel_ramp_rate=10.0,
                input_filter_bandwidth=2.0,
                torque_ramp_rate=0.01,
                mirror_ratio=1.0,
                axis_to_mirror=255,
            ),
        )
        self.encoder = _Encoder()
        self.trap_traj = types.SimpleNamespace(config=_Config(vel_limit=2.0, accel_limit=0.5, decel_limit=0.5))

    def clear_errors(self) -> None:
        self.error = 0


class _Encoder:
    """Encoder with a settable config and animated position/velocity estimates."""

    def __init__(self) -> None:
        self.config = _Config(bandwidth=1000.0)

    @property
    def pos_estimate(self) -> float:
        return _wave(4.0, 1.0)

    @property
    def vel_estimate(self) -> float:
        return _wave(4.0, 2.0)


def make_mock_odrive(serial: int = 0x208E39855253, two_axes: bool = True, control_mode: int = 2):
    """Return a fake ODrive device exposing everything ``controls()`` reads.

    ``control_mode`` sets the initial controller mode on both axes; it drives which
    motion card (torque/velocity/position) starts visible, so tests can render each.
    """
    ax0 = _MockAxis(calibrated=True, control_mode=control_mode)
    ax1 = _MockAxis(calibrated=two_axes, control_mode=control_mode)

    class _Dev:
        serial_number = serial
        hw_version_major, hw_version_minor, hw_version_variant = 3, 6, 56
        fw_version_major, fw_version_minor, fw_version_revision = 0, 5, 6
        fw_version_unreleased = 1

        def __init__(self) -> None:
            self.axis0 = ax0
            self.axis1 = ax1

        @property
        def vbus_voltage(self) -> float:
            return _wave(8.0, 0.3, 24.0)

        def save_configuration(self) -> None:
            pass

        def reboot(self) -> None:
            pass

        def clear_errors(self) -> None:  # present on 0.6.x firmware; drives the hasattr() True branch
            pass

    return _Dev()


def build_mock_page(control_mode: int = 2) -> None:
    """Build a themed test page (header + control panel) for one mock device.

    Used by ``tests/app_under_test.py`` to render the panel in a chosen ``control_mode``
    (which motion card starts visible, see ``make_mock_odrive``) — something the real
    entry point cannot be told. The dev runner ``tools/run_mock.py`` runs the real
    ``src/main.py`` instead. Imports are local because ``controls``/``theme`` live under
    ``src`` (on the path at call time) and need the odrive stub installed first.
    """
    install_odrive_stub()
    from nicegui import ui

    from controls import controls
    from theme import apply_theme, header

    dark = apply_theme()
    header(dark)
    with ui.column().classes('w-full gap-0'):  # same wrapper as main.py's per-device column
        controls(make_mock_odrive(control_mode=control_mode))


def install_odrive_stub() -> None:
    """Register fake ``odrive`` submodules so the app imports without hardware.

    Besides the ``fibre``/``utils`` bits ``controls.py`` needs, the stub carries the
    discovery API ``main.py`` uses (``start_discovery``, ``connected_devices``,
    ``connected_devices_changed``); see :func:`set_connected_devices` to drive it.
    """
    if 'odrive' in sys.modules and getattr(sys.modules['odrive'], '_is_mock', False):
        return
    odrive = types.ModuleType('odrive')
    odrive._is_mock = True  # type: ignore[attr-defined]
    odrive.default_usb_search_path = 'usb'  # type: ignore[attr-defined]
    odrive.start_discovery = lambda path: None  # type: ignore[attr-defined]
    odrive.connected_devices = []  # type: ignore[attr-defined]
    odrive.connected_devices_changed = concurrent.futures.Future()  # type: ignore[attr-defined]
    pyfibre = types.ModuleType('odrive.pyfibre')
    fibre = types.ModuleType('odrive.pyfibre.fibre')
    fibre.ObjectLostError = type('ObjectLostError', (Exception,), {})  # type: ignore[attr-defined]
    fibre.libfibre = types.SimpleNamespace(EmptyInterface=type('EmptyInterface', (), {}))
    pyfibre.fibre = fibre
    utils = types.ModuleType('odrive.utils')
    utils.dump_errors = lambda odrv, clear=False: None  # type: ignore[attr-defined]
    odrive.pyfibre = pyfibre  # type: ignore[attr-defined]
    odrive.utils = utils  # type: ignore[attr-defined]
    sys.modules.update(
        {
            'odrive': odrive,
            'odrive.pyfibre': pyfibre,
            'odrive.pyfibre.fibre': fibre,
            'odrive.utils': utils,
        }
    )


def set_connected_devices(devices: list) -> None:
    """Simulate USB hot-plugging on the stubbed ``odrive`` module.

    Replaces ``odrive.connected_devices`` and fires ``connected_devices_changed`` the way
    the real package does (a *new* future is installed before the old one resolves), so
    ``main.discovery_loop`` wakes up and reconciles.
    """
    odrive = sys.modules['odrive']
    assert getattr(odrive, '_is_mock', False), 'install_odrive_stub() must run first'
    odrive.connected_devices = list(devices)  # type: ignore[attr-defined]
    signal = odrive.connected_devices_changed  # type: ignore[attr-defined]
    odrive.connected_devices_changed = concurrent.futures.Future()  # type: ignore[attr-defined]
    if not signal.done():  # a listener that was cancelled (test teardown) leaves it cancelled
        signal.set_result(None)


def lose_mock_odrive(device: object) -> None:
    """Make ``device`` behave like a fibre object whose USB connection was lost.

    Mirrors ``RemoteObject._destroy()``: the instance's class is swapped to
    ``EmptyInterface``, so every attribute read from now on raises ``AttributeError``.
    """
    fibre = sys.modules['odrive.pyfibre.fibre']
    device.__class__ = fibre.libfibre.EmptyInterface  # type: ignore[attr-defined]


def reset_odrive_stub() -> None:
    """Forget all stub devices and pending listeners (call between tests)."""
    odrive = sys.modules['odrive']
    assert getattr(odrive, '_is_mock', False), 'install_odrive_stub() must run first'
    odrive.connected_devices = []  # type: ignore[attr-defined]
    odrive.connected_devices_changed = concurrent.futures.Future()  # type: ignore[attr-defined]


def arrive_mid_scan(during: object, arriving: object) -> dict:
    """Hot-plug ``arriving`` while the discovery loop reads ``during``'s serial number.

    That read happens *inside* the scan — the window in which the real ``odrive`` installs a
    fresh ``connected_devices_changed`` before resolving the old one. A loop that reads the
    attribute after scanning therefore awaits the replacement and never wakes up.
    Patches the class, which ``make_mock_odrive`` builds fresh per device. One-shot per
    device: do not re-arm ``during`` while a trap is still pending — the serial read below
    would spring it, hot-plugging the previous pair right here instead of mid-scan.

    Returns a report whose ``fired_mid_scan`` says whether the trap really sprang inside
    ``discovery_loop``'s scan (before ``during`` reached its registry). Assert it at the end
    of the test: nothing else guarantees the loop's scan is the first serial read, and if a
    refactor moves that read the trap would spring at, say, panel render — turning the test
    into an ordinary hot-plug test that passes even with the race reintroduced.
    """
    serial = during.serial_number
    report = {'fired_mid_scan': False}

    def read_once(self) -> int:
        type(self).serial_number = serial  # fire on the first read only
        scan = sys._getframe(1)  # the frame whose read sprang the trap
        report['fired_mid_scan'] = scan.f_code.co_name == 'discovery_loop' and serial not in scan.f_globals.get('devices', {})
        set_connected_devices([during, arriving])
        return serial

    type(during).serial_number = property(read_once)  # type: ignore[misc]
    return report
