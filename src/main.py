#!/usr/bin/env python3
from nicegui import ui
import odrive
from odrive.utils import dump_errors

odrv = odrive.find_any()

ui.label('Hello ODrive!!!')

voltage = ui.label()
ui.timer(1.0, lambda: voltage.set_text(f'Voltage: {odrv.vbus_voltage:.2f} V'))

ui.button('Dump errors', on_click=lambda: dump_errors(odrv, True))
