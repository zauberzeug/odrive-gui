#!/usr/bin/env python3
"""ODrive GUI — a web UI to tune and debug ODrive motor controllers.

Discovers ODrives on the USB bus and renders one live control panel per device,
adding and removing panels as devices connect and disconnect.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import odrive
from nicegui import app, ui

from controls import controls, is_lost
from theme import apply_theme, header

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('odrive_gui')
log.setLevel(logging.INFO)

# The connected devices, keyed by serial number. Maintained by discovery_loop() and
# shared by all clients; every page renders its own panels from it. Nothing UI-related
# may live at module scope: with NiceGUI 3.x that would switch on "script mode", where
# the module is re-executed per page request and the startup loop's elements belong to
# a throw-away client no browser ever sees.
devices: dict[int, Any] = {}


@ui.refreshable
def device_panels() -> None:
    """One full-width panel per connected device, or a placeholder if there is none.

    Called once per page (per client) and refreshed for all clients whenever the set
    of connected devices changes.
    """
    if not devices:
        ui.markdown('Waiting for ODrive devices to connect…').classes('p-4')
    for serial, device in devices.items():
        # each panel starts with its info strip docked under the header (or under the
        # previous device's cards).
        column = ui.column().classes('w-full gap-0')
        try:
            with column:
                controls(device)
        except Exception as e:
            if not is_lost(e):
                raise
            # the device left the bus during the (many) live reads of the build; the next
            # discovery event drops it from the registry and refreshes all clients.
            log.info('ODrive %x left the bus while building its panel', serial)
            column.delete()


@ui.page('/')
def index() -> None:
    dark = apply_theme()
    header(dark)
    device_panels()


async def discovery_loop() -> None:
    """Keep ``devices`` in sync with the USB bus and refresh every client on a change."""
    odrive.start_discovery(odrive.default_usb_search_path)
    while True:
        # grab the signal *before* scanning: odrive swaps in a new future on every
        # (dis)connect, so taking it afterwards would miss an event that fires mid-scan.
        changed = odrive.connected_devices_changed
        connected: dict[int, Any] = {}
        for device in list(odrive.connected_devices):  # snapshot: mutated from the fibre thread
            try:
                connected[device.serial_number] = device
            except Exception as e:
                if not is_lost(e):
                    raise
                # went away between the scan and the read; the next event catches up
        if [(s, id(d)) for s, d in connected.items()] != [(s, id(d)) for s, d in devices.items()]:
            for serial in devices.keys() - connected.keys():
                log.info('Removing ODrive %x', serial)
            for serial in connected.keys() - devices.keys():
                log.info('Adding ODrive %x', serial)
            devices.clear()
            devices.update(connected)
            try:
                await device_panels.refresh()
            except Exception:
                log.exception('Failed to rebuild the device panels')
        await asyncio.wrap_future(changed)


app.on_startup(discovery_loop)

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='ODrive Motor Tuning', favicon='⚙️')
