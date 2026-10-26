"""Hardware-free tests for the control panel against a mock ODrive.

Two layers of safety net, neither of which needs a real ODrive:
- render tests prove the panel *builds* (every widget/binding is constructed);
- a plot/telemetry test lets the live timers read every device attribute the UI *reads*
  from the mock, and a handler test runs every ``on_click`` against it, so a broken
  attribute path or handler fails CI instead of only surfacing when hardware is plugged in.
"""

import asyncio
import threading

from mock_odrive import READS
from nicegui import ui
from nicegui.testing import User

from controls import _Mirror, _usb


async def test_panel_renders(user: User) -> None:
    await user.open('/')
    await user.should_see('Axis 0')
    await user.should_see('Axis 1')
    await user.should_see('SN 208E39855253')


async def test_modes_and_gains_present(user: User) -> None:
    await user.open('/')
    await user.should_see('P-filter')  # INPUT_MODES toggle option
    await user.should_see('pos_gain')
    await user.should_see('current_lim')
    await user.should_see('Live plots')


async def test_action_buttons_run_without_error(user: User) -> None:
    """Fire ``click`` on every button so the save/reboot/dump/clear/motion ``on_click``
    handlers execute against the mock. The NiceGUI ``user`` fixture fails the test on any
    ERROR log, and a raising handler is logged via ``app.handle_exception`` — so a bad
    attribute path, arity or the empty-field ``TypeError`` is caught here.

    Two things this has to get right, both of which silently narrowed the old coverage:
    - ``.trigger('click')`` fires the event on *all* found buttons; ``.click()`` only
      dispatches to the single lowest-id element (here the save button), so the motion
      handlers were never invoked at all under ``.click()``.
    - ``User.find`` returns only *visible* elements, and each control mode hides two of the
      three motion cards — so we render every mode in turn, else ``send_torque`` /
      ``send_position`` stay hidden behind the default velocity mode.
    (control_mode: 1=torque, 2=velocity, 3=position — see ``MODES`` in controls.py.)"""
    for mode in (1, 2, 3):
        await user.open(f'/mode/{mode}')
        user.find(ui.button).trigger('click')


async def test_live_plots_and_telemetry_read_the_mock(user: User) -> None:
    """Enable every plot and let the timers run: the plot samplers and the telemetry
    labels then read every device path the UI uses against the mock (CLAUDE.md mirroring
    rule), and the ``user`` fixture fails on the ERROR a broken path would log. Unlike a
    hand-copied list of paths, this cannot drift from what the UI actually reads."""
    await user.open('/')
    checks = user.find(ui.checkbox).elements
    assert len(checks) == 10  # 5 plots x 2 axes
    for check in checks:
        check.set_value(True)
    await asyncio.sleep(0.3)  # several 20 Hz plot pushes and 10 Hz power-label updates
    for check in checks:
        check.set_value(False)
    await asyncio.sleep(0.1)  # the per-axis plot timers are torn down without error


async def test_live_values_are_not_read_on_the_event_loop(user: User) -> None:
    """Every device read is a blocking USB round-trip, so after the panel is built none may
    happen on the event loop: widgets bind to local mirrors that a worker thread refreshes.
    Bound straight to the fibre objects instead, NiceGUI's binding loop polls each of them
    on the loop every 0.1 s (two calibrated axes: ~440 USB reads per second)."""
    await user.open('/')
    await user.should_see('Axis 1')
    loop_thread = threading.current_thread().name
    before = READS.copy()
    await asyncio.sleep(1.2)  # several binding refreshes and mirror syncs, every 10 Hz/1 Hz timer
    assert READS[loop_thread] == before[loop_thread]
    assert READS['odrive-usb_0'] > before['odrive-usb_0']  # the live values are still read, on the worker


async def test_a_refresh_that_read_before_an_edit_does_not_undo_it(user: User, mock_odrive) -> None:
    """A refresh reads on the USB worker while the user may edit the same value: the read
    sees the old device value, and applying it would snap the widget back -- whose change
    handler then writes the old value to the device too. Holding the worker makes the
    read-queued-before-the-write order deterministic."""
    config = mock_odrive.axis0.controller.config
    mirror = _Mirror(config)
    assert mirror.pos_gain == 20.0  # registers pos_gain for refreshes
    gate = threading.Event()
    _usb.submit(gate.wait)
    sync = asyncio.create_task(mirror.sync())
    await asyncio.sleep(0.01)  # the refresh's read is now queued behind the gate
    mirror.pos_gain = 42.0  # and the write behind it
    gate.set()
    await sync
    await asyncio.sleep(0.05)
    assert mirror.pos_gain == 42.0
    assert config.pos_gain == 42.0
