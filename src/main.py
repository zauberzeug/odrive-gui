#!/usr/bin/env python3
from typing import Any
from nicegui import ui
import odrive
from odrive.utils import dump_errors

odrv = odrive.find_any()

ui.label('ODrive', 'h4')

with ui.row().add_classes('items-center'):
    ui.label(f'SN {hex(odrv.serial_number).removeprefix("0x").upper()}')
    ui.label(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
    ui.label(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision} ' +
             f'{"(dev)" if odrv.fw_version_unreleased else ""}')
    voltage = ui.label()
    ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
    ui.button(icon='bug_report', design='flat round', on_click=lambda: dump_errors(odrv, True))

def axis_column(a: int, axis: Any):

    ui.label(f'Axis {a}', 'h5')

    ui.label(f'Error: {axis.error:x}' if axis.error else '')

    ui.label('Settings', 'h6')

    for obj, key in [
        (axis.controller.config, 'pos_gain'),
        (axis.controller.config, 'vel_gain'),
        (axis.controller.config, 'vel_integrator_gain'),
        (axis.controller.config, 'vel_limit'),
        (axis.encoder.config, 'bandwidth'),
    ]:
        ui.number(label=key, value=getattr(obj, key), decimals=3,
                  design='outlined', on_change=lambda e: setattr(obj, key, e.value))

with ui.row():
    for a, axis in enumerate([odrv.axis0, odrv.axis1]):
        with ui.column():
            axis_column(a, axis)
