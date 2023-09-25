#!/usr/bin/env python3
import asyncio
import logging

import odrive
from nicegui import app, ui

from controls import controls

logging.getLogger('nicegui').setLevel(logging.ERROR)

ui.colors(primary='#6e93d6')

devices: dict[int, ui.element] = {}

ui.markdown('## ODrive GUI')
ui.markdown('Waiting for ODrive devices to connect...').bind_visibility_from(globals(), 'devices', lambda d: not d)
container = ui.row()


async def discovery_loop() -> None:
    odrive.start_discovery(odrive.default_usb_search_path)
    while True:
        for device in odrive.connected_devices:
            if device.serial_number not in devices:
                print(f'Adding ODrive {device.serial_number:x}')
                with container:
                    with ui.column() as devices[device.serial_number]:
                        controls(device)
        for serial_number in list(devices):
            if not any(d.serial_number == serial_number for d in odrive.connected_devices):
                print(f'Removing ODrive {serial_number:x}')
                container.remove(devices.pop(serial_number))
        await asyncio.wrap_future(odrive.connected_devices_changed)


app.on_startup(discovery_loop())

ui.run(title='ODrive Motor Tuning')
