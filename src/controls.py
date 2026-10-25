"""Per-device control panel for a connected ODrive.

``controls(odrv)`` renders the full tuning UI for one ODrive: a header with
identity/telemetry and global actions, then one card per calibrated axis with
mode/state toggles, live input controls, gains, limits and live plots.

The ``odrv`` argument is a live `fibre` remote object, so it is dynamically
typed (``Any``); every attribute accessed here mirrors the ODrive 0.5.x/0.6.x
object tree. A faithful in-memory stand-in lives in ``tools/mock_odrive.py`` for
hardware-free runs and tests.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any

from nicegui import ui
from odrive.pyfibre import fibre
from odrive.utils import dump_errors

log = logging.getLogger('odrive_gui')

MODES: dict[int, str] = {
    0: 'Voltage',
    1: 'Torque',
    2: 'Velocity',
    3: 'Position',
}

INPUT_MODES: dict[int, str] = {
    0: 'Inactive',
    1: 'Through',
    2: 'V-ramp',
    3: 'P-filter',
    5: 'Trap traj',
    6: 'T-ramp',
    7: 'Mirror',
}

STATES: dict[int, str] = {
    0: 'Undefined',
    1: 'Idle',
    8: 'Loop',
}


def _lost(obj: Any) -> bool:
    """Whether fibre has already torn ``obj`` down (its USB connection was lost).

    libfibre swaps a lost object's class to ``EmptyInterface`` on its own thread, after
    which every attribute read raises ``AttributeError``. The panel's timers can fire in
    the short window before the discovery loop deletes the panel, so they check first.
    """
    return obj.__class__ is fibre.libfibre.EmptyInterface


# Every device read or write is a blocking USB round-trip. After the panel is built, all of
# them run on this one worker, in the order they were issued: the event loop never waits for
# the bus, and a command can never overtake a setting the user changed before it.
_usb = ThreadPoolExecutor(max_workers=1, thread_name_prefix='odrive-usb')
_write_order = itertools.count()


def _send(obj: Any, fn: Callable[[], Any]) -> None:
    """Queue ``fn()`` (a write or command) on the USB worker; log it if it fails."""

    def done(future: Future) -> None:
        e = future.exception()
        if e is not None and not (isinstance(e, fibre.ObjectLostError) or _lost(obj)):
            log.error('ODrive write failed', exc_info=e)

    _usb.submit(fn).add_done_callback(done)


async def _on_usb(obj: Any, fn: Callable[[], Any]) -> Any:
    """``fn()`` on the USB worker; ``None`` if ``obj``'s device left the bus meanwhile."""
    try:
        return await asyncio.get_running_loop().run_in_executor(_usb, fn)
    except Exception as e:
        if isinstance(e, fibre.ObjectLostError) or _lost(obj):
            return None
        raise


class _Mirror:
    """A local copy of the attributes widgets bind to on one fibre object.

    NiceGUI cannot be notified by a fibre object, so it polls every bound attribute each
    0.1 s -- on the event loop. Widgets bind to this mirror instead: reading it is free,
    ``sync()`` refreshes it on the USB worker, and a widget's change is written through there.
    """

    def __init__(self, obj: Any) -> None:
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_values', {})
        object.__setattr__(self, '_written', {})  # name -> _write_order of its last write

    def __getattr__(self, name: str) -> Any:
        if name not in self._values:
            self._values[name] = getattr(self._obj, name)  # first read, while building the panel
        return self._values[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self._values[name] = value
        self._written[name] = next(_write_order)
        _send(self._obj, lambda: setattr(self._obj, name, value))

    async def sync(self) -> None:
        names = list(self._values)
        start = next(_write_order)
        values = await _on_usb(self._obj, lambda: [getattr(self._obj, name) for name in names])
        for name, value in zip(names, values or [], strict=False):
            # a write queued after this read started is newer than what the read saw
            if self._written.get(name, -1) < start:
                self._values[name] = value


def controls(odrv: Any) -> None:
    """Render the control panel for a single connected ODrive device."""

    # Read the serial once, while the device is guaranteed on the bus. Reused for the SN
    # chip and the reboot log so reboot() never does a live read on `odrv` — that read
    # would raise ObjectLostError if the panel outlived the device leaving the bus, and
    # it saves a blocking USB round-trip per reboot click.
    serial = odrv.serial_number

    def reboot() -> None:
        try:
            odrv.reboot()
        except fibre.ObjectLostError:
            # the device drops off the USB bus mid-reboot; that specific loss is expected.
            # do NOT touch `odrv` here — a live read on the just-disconnected device raises again.
            log.info('ODrive %x rebooting (connection dropped as expected)', serial)

    with ui.row().classes('w-full items-center justify-between gap-4 gui-strip'):
        with ui.row().classes('items-center gap-4'):
            _chip(f'SN {hex(serial).removeprefix("0x").upper()}')
            _chip(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
            _chip(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision}{" (dev)" if odrv.fw_version_unreleased else ""}')
            voltage = ui.label().classes('text-lg font-medium text-primary')

            async def update_voltage() -> None:
                if (vbus := await _on_usb(odrv, lambda: odrv.vbus_voltage)) is not None:
                    voltage.set_text(f'{vbus:.2f} V')

            ui.timer(1.0, update_voltage)
        with ui.row().classes('gap-1'):
            # wrap in a lambda (like the original): passing the bare fibre RemoteFunction makes
            # NiceGUI introspect its signature, which is brittle on the C-backed proxy.
            ui.button(icon='save', on_click=lambda: _send(odrv, lambda: odrv.save_configuration())).props('dense').tooltip('Save configuration')
            ui.button(icon='bug_report', on_click=lambda: _send(odrv, lambda: dump_errors(odrv, hasattr(odrv, 'clear_errors')))).props(
                'dense'
            ).tooltip('Dump and clear errors')
            ui.button(icon='restart_alt', on_click=lambda: _send(odrv, reboot)).props('dense').tooltip('Reboot ODrive')

    with ui.row().classes('gap-4 items-stretch p-4'):
        for index, axis in enumerate([odrv.axis0, odrv.axis1]):
            if not axis.motor.is_calibrated:
                continue
            with ui.card().props('flat bordered'), ui.column():
                _create_axis_column(index, axis)


def _chip(text: str) -> ui.label:
    """A device identity value (serial, HW/FW version): plain monospace, no box."""
    return ui.label(text).classes('text-sm font-mono opacity-80')


def _field_value(field: ui.number) -> float:
    """The field's value, with an empty field (``None``) read as 0 — so *stop* on a
    spinning motor still writes 0 even if the input box was cleared."""
    return float(field.value or 0)


def _create_axis_column(index: int, axis: Any) -> None:
    with ui.row().classes('w-full items-center justify-between'):
        ui.label(f'Axis {index}').classes('text-xl font-medium')
        with ui.row().classes('items-center gap-2'):
            power = ui.label()
            # access via lambda, not `on_click=axis.clear_errors`: the method is optional on
            # older firmware, so it must not be read until the button (if shown) is clicked.
            button = (
                ui.button(icon='bug_report', color='negative', on_click=lambda: _send(axis, lambda: axis.clear_errors()))
                .props('dense')
                .tooltip('Clear errors')
            )
            button.set_visibility(hasattr(axis, 'clear_errors'))

    mirrors = [_Mirror(obj) for obj in (axis, axis.controller.config, axis.motor.config, axis.encoder.config, axis.trap_traj.config)]
    axis_state, ctr_cfg, mtr_cfg, enc_cfg, trp_cfg = mirrors
    cc = axis.motor.current_control

    async def sync_mirrors() -> None:
        for mirror in mirrors:
            await mirror.sync()
        show_state(axis_state.current_state)

    async def update_power() -> None:
        if (watts := await _on_usb(axis, lambda: cc.Iq_measured * cc.v_current_control_integral_q)) is not None:
            power.set_text(f'{watts:.1f} W')

    async def update_error() -> None:
        if (error := await _on_usb(axis, lambda: axis.error)) is not None:
            button.set_enabled(error != 0)

    # every property read is a USB round-trip, so keep the 10 Hz path to the two values
    # that must feel live; the error flag only enables a button and can follow at 1 Hz.
    ui.timer(0.1, update_power)
    ui.timer(0.1, sync_mirrors)
    ui.timer(1.0, update_error)

    def request_state(state: int) -> None:
        _send(axis, lambda: setattr(axis, 'requested_state', state))

    # The axis state is one button per state, not a toggle: every click must reach the
    # device, but a toggle drops a click on the option it already shows -- and the state
    # shown can be a refresh old (the firmware has not switched yet), so that click can be
    # the Idle that stops a motor. A toggle's value changes are no better a trigger: they
    # also fire when a refresh shows the device's state, and writing that back re-requested
    # e.g. CLOSED_LOOP for an axis already in it, which makes 0.5.x firmware leave and
    # re-enter closed loop (a brief disarm of a live motor). So clicks request, refreshes show.
    state_buttons: dict[int, ui.button] = {}
    shown: list[int | None] = [None]

    def show_state(state: int) -> None:
        if state == shown[0]:
            return
        shown[0] = state
        for value, state_button in state_buttons.items():
            state_button.props(remove='flat unelevated color')
            state_button.props('unelevated color=primary' if value == state else 'flat')

    with ui.row().classes('gap-2'):
        mode = ui.toggle(MODES).bind_value(ctr_cfg, 'control_mode')
        with ui.element('div').classes('q-btn-toggle row no-wrap inline'):
            for value, label in STATES.items():
                state_buttons[value] = ui.button(label, on_click=lambda value=value: request_state(value)).props(remove='round').props('no-caps')
        show_state(axis_state.current_state)

    with ui.row().classes('gap-4 items-start'):
        for value, name, attr, icons in _MOTION_INPUTS:
            with ui.column().classes('gap-1').bind_visibility_from(mode, 'value', value=value):
                _motion_input(axis, name, attr, icons)

        with ui.column().classes('gap-1'):
            ui.markdown('**Gains**')
            ui.number('pos_gain', format='%.3f').bind_value(ctr_cfg, 'pos_gain')
            ui.number('vel_gain', format='%.3f').bind_value(ctr_cfg, 'vel_gain')
            ui.number('vel_integrator_gain', format='%.3f').bind_value(ctr_cfg, 'vel_integrator_gain')
            if hasattr(ctr_cfg, 'vel_differentiator_gain'):
                ui.number('vel_differentiator_gain', format='%.3f').bind_value(ctr_cfg, 'vel_differentiator_gain')

        with ui.column().classes('gap-1'):
            ui.markdown('**Limits & bandwidth**')
            ui.number('vel_limit', format='%.3f').bind_value(ctr_cfg, 'vel_limit')
            ui.number('enc_bandwidth', format='%.3f').bind_value(enc_cfg, 'bandwidth')
            ui.number('current_lim', format='%.1f').bind_value(mtr_cfg, 'current_lim')
            ui.number('cur_bandwidth', format='%.3f').bind_value(mtr_cfg, 'current_control_bandwidth')
            ui.number('torque_lim', format='%.1f').bind_value(mtr_cfg, 'torque_lim')
            ui.number('requested_cur_range', format='%.1f').bind_value(mtr_cfg, 'requested_current_range')

    input_mode = ui.toggle(INPUT_MODES).bind_value(ctr_cfg, 'input_mode')
    with ui.row().classes('gap-2 items-start'):
        ui.number('inertia', format='%.3f').bind_value(ctr_cfg, 'inertia').bind_visibility_from(
            input_mode, 'value', backward=lambda m: m in [2, 3, 5]
        )
        ui.number('velocity ramp rate', format='%.3f').bind_value(ctr_cfg, 'vel_ramp_rate').bind_visibility_from(input_mode, 'value', value=2)
        ui.number('input filter bandwidth', format='%.3f').bind_value(ctr_cfg, 'input_filter_bandwidth').bind_visibility_from(
            input_mode, 'value', value=3
        )
        with ui.row().classes('gap-2').bind_visibility_from(input_mode, 'value', value=5):
            ui.number('trajectory velocity limit', format='%.3f').bind_value(trp_cfg, 'vel_limit')
            ui.number('trajectory acceleration limit', format='%.3f').bind_value(trp_cfg, 'accel_limit')
            ui.number('trajectory deceleration limit', format='%.3f').bind_value(trp_cfg, 'decel_limit')
        ui.number('torque ramp rate', format='%.3f').bind_value(ctr_cfg, 'torque_ramp_rate').bind_visibility_from(input_mode, 'value', value=6)
        ui.number('mirror ratio', format='%.3f').bind_value(ctr_cfg, 'mirror_ratio').bind_visibility_from(input_mode, 'value', value=7)
        ui.toggle({0: 'Axis 0', 1: 'Axis 1'}).bind_value(ctr_cfg, 'axis_to_mirror', forward=lambda x: 255 if x is None else x).bind_visibility_from(
            input_mode, 'value', value=7
        )

    with ui.expansion('Live plots', icon='show_chart').classes('w-full'):
        _live_plots(axis)


# the torque / velocity / position inputs: (control_mode value, label, controller attribute, icons)
_MOTION_INPUTS: list[tuple[int, str, str, tuple[str, str, str]]] = [
    (1, 'Torque', 'input_torque', ('remove', 'radio_button_unchecked', 'add')),
    (2, 'Velocity', 'input_vel', ('fast_rewind', 'stop', 'fast_forward')),
    (3, 'Position', 'input_pos', ('skip_previous', 'exposure_zero', 'skip_next')),
]


def _motion_input(axis: Any, name: str, attr: str, icons: tuple[str, str, str]) -> None:
    """A labelled number field plus -/0/+ buttons that write ``sign * value`` to ``axis.controller.<attr>``."""
    ui.markdown(f'**{name}**')
    field = ui.number(f'input {name.lower()}', value=0)

    def send(sign: int) -> None:
        value = sign * _field_value(field)
        _send(axis, lambda: setattr(axis.controller, attr, value))

    with ui.row().classes('w-full justify-around gap-0'):
        for icon, sign in zip(icons, (-1, 0, 1), strict=True):
            ui.button(icon=icon, on_click=lambda sign=sign: send(sign))


def _live_plots(axis: Any) -> None:
    """Checkbox-gated live plots. One 20 Hz timer per axis samples the device for every
    enabled plot, and it only exists while at least one plot is enabled — an idle
    NiceGUI timer still wakes every interval, and five per axis added up."""
    cc = axis.motor.current_control
    plots: list[tuple[ui.checkbox, ui.line_plot, Callable[[], list[list[float]]]]] = []
    timer: ui.timer | None = None

    async def push() -> None:
        now = datetime.now()
        shown = [(plot, sample) for check, plot, sample in plots if check.value]
        samples = await _on_usb(axis, lambda: [sample() for _, sample in shown])
        for (plot, _), values in zip(shown, samples or [], strict=False):
            # line_plot uses a datetime x-axis (matplotlib handles it); the stub types x as float.
            plot.push([now], values)  # type: ignore[list-item]

    def update_timer() -> None:
        nonlocal timer
        if any(check.value for check, _, _ in plots):
            if timer is None:
                timer = ui.timer(0.05, push)
        elif timer is not None:
            timer.cancel()
            timer.delete()
            timer = None

    for name, legend, sample in (
        ('Position', ['input_pos', 'pos_estimate'], lambda: [[axis.controller.input_pos], [axis.encoder.pos_estimate]]),
        ('Velocity', ['input_vel', 'vel_estimate'], lambda: [[axis.controller.input_vel], [axis.encoder.vel_estimate]]),
        ('Id', ['Id_setpoint', 'Id_measured'], lambda: [[cc.Id_setpoint], [cc.Id_measured]]),
        ('Iq', ['Iq_setpoint', 'Iq_measured'], lambda: [[cc.Iq_setpoint], [cc.Iq_measured]]),
        ('Temperature', ['fet_temperature'], lambda: [[axis.motor.fet_thermistor.temperature]]),
    ):
        check = ui.checkbox(f'{name} plot', on_change=update_timer)
        plot = ui.line_plot(n=len(legend), update_every=10).with_legend(legend, loc='upper left', ncol=2)
        check.bind_value_to(plot, 'visible')
        plots.append((check, plot, sample))
