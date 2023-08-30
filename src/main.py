#!/usr/bin/env python3
import asyncio
import logging

import odrive
from nicegui import app, ui

from controls import controls

logging.getLogger("nicegui").setLevel(logging.ERROR)

ui.colors(primary='#6e93d6')

ui.markdown('## ODrive GUI')
message = ui.markdown()
container = ui.row()


def show_message(text: str) -> None:
    message.content = text
    print(text, flush=True)

known_devices = {}
active_devices = {}

async def discovery_loop():
    show_message('# Connecting to ODrives...')
    odrive.start_discovery(odrive.default_usb_search_path)
    while True:
        signal = odrive.connected_devices_changed
        if len(odrive.connected_devices) > len(known_devices):
            # A device is connected for which no controller is currently active
            device = odrive.connected_devices[-1]
            serial = hex(device.serial_number)
            print(f'Adding ODrive {serial}')
            with container:
                with ui.column() as element:
                    controls(device)
            known_devices[serial] = element
            # Move it to the correct position
            ordered_devices = sorted(list(known_devices.keys()))
            target_index = ordered_devices.index(serial)
            element.move(target_index=target_index)
            message.visible = False
        elif len(odrive.connected_devices) < len(known_devices):
            # a device for which we're rendering an active controller is not connected anymore
            # find out which one
            remaining_serials = remaining_serials = [hex(device.serial_number) for device in odrive.connected_devices]
            lost_serials = [serial_number for serial_number in known_devices if serial_number not in remaining_serials]
            # deactivate the controllers for the lost devices
            for lost_serial in lost_serials:
                print(f'Removing ODrive {lost_serial}')
                container.remove(known_devices[lost_serial])
                del known_devices[lost_serial]
        await asyncio.wrap_future(signal)

async def startup() -> None:
        asyncio.create_task(discovery_loop())

app.on_startup(startup)

ui.run(title='ODrive Motor Tuning')
