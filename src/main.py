#!/usr/bin/env python3
import asyncio
import functools

import libusb_package
import odrive
import usb.util
from nicegui import app, ui

from controls import controls

ui.colors(primary='#6e93d6')

ui.markdown('## ODrive GUI')
message = ui.markdown()
container = ui.column()


def show_message(text: str) -> None:
    message.content = text
    print(text, flush=True)

# List all all connected odrives
devices = list(libusb_package.find(idVendor=0x1209, idProduct=0x0D32, find_all=True))
if len(devices) == 0:
    print("No devices found")
    exit()

# Get the serials and sort them so that we get a predictable display order
serials = sorted(list(map(lambda device: usb.util.get_string(device, device.iSerialNumber), devices)))

async def startup() -> None:
        show_message('# Connecting to ODrives...')
        odrives = []
        for serial in serials:
            try:
                loop = asyncio.get_running_loop()
                odrv = await loop.run_in_executor(None, functools.partial(odrive.find_any, serial_number=serial, timeout=15))
                print("have odrive " + hex(odrv.serial_number))
                odrives.append(odrv)
            except TimeoutError:
                show_message(f'# Could not connect to ODrive {serial}')
        message.visible = False
        with container:
            for odrv in odrives:
                controls(odrv)

app.on_startup(startup)

ui.run(title='ODrive Motor Tuning')
