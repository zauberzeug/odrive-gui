#!/usr/bin/env python3
from nicegui import ui
import odrive
from odrive.utils import dump_errors
from typing import Any
from datetime import datetime

odrv = odrive.find_any()

modes = {
    0: 'voltage',
    1: 'torque',
    2: 'velocity',
    3: 'position',
}

states = {
    0: 'undefined',
    1: 'idle',
    2: 'startup sequence',
    3: 'full calibration sequence',
    4: 'motor calibration',
    5: 'sensorless control',
    6: 'encoder index search',
    7: 'encoder offset calibration',
    8: 'closed loop control',
    9: 'lockin spin',
    10: 'encoder dir find',
    11: 'homing',
}

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

    ctr_cfg = axis.controller.config
    enc_cfg = axis.encoder.config

    mode = ui.toggle(modes).bind_value(ctr_cfg.control_mode)

    with ui.row().add_classes('items-center'):
        ui.label('State:')
        ui.select(states, on_change=lambda e: setattr(axis, 'requested_state', e.value.value)) \
            .bind_value_from(axis.current_state)

    params = {'format': '%.3f', 'design': 'outlined'}
    with ui.row():
        ui.number(label='pos_gain', **params).bind_value(ctr_cfg.pos_gain)
        ui.number(label='vel_limit', **params).bind_value(ctr_cfg.vel_limit)
    with ui.row():
        ui.number(label='vel_gain', **params).bind_value(ctr_cfg.vel_gain)
        ui.number(label='bandwidth', **params).bind_value(enc_cfg.bandwidth)
    with ui.row():
        ui.number(label='vel_integrator_gain', **params).bind_value(ctr_cfg.vel_integrator_gain)

    pos_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_pos', 'pos_estimate'], loc='upper left', ncol=2)
    ui.timer(0.05, lambda: pos_plot.push([datetime.now()], [[axis.controller.input_pos], [axis.encoder.pos_estimate]]))

    vel_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_vel', 'vel_estimate'], loc='upper left', ncol=2)
    ui.timer(0.05, lambda: vel_plot.push([datetime.now()], [[axis.controller.input_vel], [axis.encoder.vel_estimate]]))

    with ui.row():

        with ui.column():

            with ui.card().bind_visibility_from(mode.value, backward=lambda m: m == 1):

                ui.label('Torque', 'bold')

                torque = type('', (), {"value": 0})()
                ui.number(label='input torque').bind_value(torque.value)

                def send_torque(sign: int):
                    axis.controller.input_torque = sign * float(torque.value)
                with ui.row():
                    ui.button(design='round flat', icon='remove', on_click=lambda: send_torque(-1))
                    ui.button(design='round flat', icon='radio_button_unchecked', on_click=lambda: send_torque(0))
                    ui.button(design='round flat', icon='add', on_click=lambda: send_torque(1))

            with ui.card().bind_visibility_from(mode.value, backward=lambda m: m == 2):

                ui.label('Velocity', 'bold')

                velocity = type('', (), {"value": 0})()
                ui.number(label='input velocity').bind_value(velocity.value)

                def send_velocity(sign: int):
                    axis.controller.input_vel = sign * float(velocity.value)
                with ui.row():
                    ui.button(design='round flat', icon='fast_rewind', on_click=lambda: send_velocity(-1))
                    ui.button(design='round flat', icon='stop', on_click=lambda: send_velocity(0))
                    ui.button(design='round flat', icon='fast_forward', on_click=lambda: send_velocity(1))

            with ui.card().bind_visibility_from(mode.value, backward=lambda m: m == 3):

                ui.label('Position', 'bold')

                position = type('', (), {"value": 0})()
                ui.number(label='input position').bind_value(position.value)

                def send_position(sign: int):
                    axis.controller.input_pos = sign * float(position.value)
                with ui.row():
                    ui.button(design='round flat', icon='skip_previous', on_click=lambda: send_position(-1))
                    ui.button(design='round flat', icon='exposure_zero', on_click=lambda: send_position(0))
                    ui.button(design='round flat', icon='skip_next', on_click=lambda: send_position(1))

        with ui.column():
            ui.button('idle', icon='stop', on_click=lambda: setattr(axis, 'requested_state', 1))
            ui.button('loop', icon='play_arrow', on_click=lambda: setattr(axis, 'requested_state', 8))

with ui.row():
    for a, axis in enumerate([odrv.axis0, odrv.axis1]):
        with ui.card(), ui.column():
            axis_column(a, axis)
