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

input_modes = {
    0: 'inactive',
    1: 'through',
    2: 'v-ramp',
    3: 'p-filter',
    5: 'trap traj',
    6: 't-ramp',
    7: 'mirror',
}

states = {
    0: 'undefined',
    1: 'idle',
    8: 'loop',
}

ui.label('ODrive', 'h4')

with ui.row().add_classes('items-center'):
    ui.label(f'SN {hex(odrv.serial_number).removeprefix("0x").upper()}')
    ui.label(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
    ui.label(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision} ' +
             f'{"(dev)" if odrv.fw_version_unreleased else ""}')
    voltage = ui.label()
    ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
    ui.button(icon='save', design='flat round', on_click=lambda: odrv.save_configuration())
    ui.button(icon='bug_report', design='flat round', on_click=lambda: dump_errors(odrv, True))

def axis_column(a: int, axis: Any):

    ui.label(f'Axis {a}', 'h5')

    ctr_cfg = axis.controller.config
    enc_cfg = axis.encoder.config
    trp_cfg = axis.trap_traj.config

    with ui.row():
        mode = ui.toggle(modes).bind_value(ctr_cfg.control_mode)
        ui.toggle(states) \
            .bind_value_to(axis.requested_state, forward=lambda x: x or 0) \
            .bind_value_from(axis.current_state)

    params = {'format': '%.3f', 'design': 'outlined'}

    with ui.row():

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

            ui.number(label='pos_gain', **params).bind_value(ctr_cfg.pos_gain)
            ui.number(label='vel_gain', **params).bind_value(ctr_cfg.vel_gain)
            ui.number(label='vel_integrator_gain', **params).bind_value(ctr_cfg.vel_integrator_gain)

        with ui.column():

            ui.number(label='vel_limit', **params).bind_value(ctr_cfg.vel_limit)
            ui.number(label='bandwidth', **params).bind_value(enc_cfg.bandwidth)

    input_mode = ui.toggle(input_modes).bind_value(ctr_cfg.input_mode)
    with ui.row():
        ui.number(label='inertia', **params).bind_value(ctr_cfg.inertia) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m in [2, 3, 5])
        ui.number(label='velocity ramp rate', **params).bind_value(ctr_cfg.vel_ramp_rate) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 2)
        ui.number(label='input filter bandwidth', **params).bind_value(ctr_cfg.input_filter_bandwidth) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 3)
        ui.number(label='trajectory velocity limit', **params).bind_value(trp_cfg.vel_limit) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 5)
        ui.number(label='trajectory acceleration limit', **params).bind_value(trp_cfg.accel_limit) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 5)
        ui.number(label='trajectory deceleration limit', **params).bind_value(trp_cfg.decel_limit) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 5)
        ui.number(label='torque ramp rate', **params).bind_value(ctr_cfg.torque_ramp_rate) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 6)
        ui.number(label='mirror ratio', **params).bind_value(ctr_cfg.mirror_ratio) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 7)
        ui.toggle({0: 'axis 0', 1: 'axis 1'}).bind_value(ctr_cfg.axis_to_mirror) \
            .bind_visibility_from(input_mode.value, backward=lambda m: m == 7)

    pos_check = ui.checkbox('Position plot', value=True)
    pos_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_pos', 'pos_estimate'], loc='upper left', ncol=2)
    def pos_push(): return pos_plot.push([datetime.now()], [[axis.controller.input_pos], [axis.encoder.pos_estimate]])
    pos_timer = ui.timer(0.05, pos_push)
    pos_check.bind_value_to(pos_plot.visible).bind_value_to(pos_timer.active)

    vel_check = ui.checkbox('Velocity plot', value=False)
    vel_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_vel', 'vel_estimate'], loc='upper left', ncol=2)
    def vel_push(): return vel_plot.push([datetime.now()], [[axis.controller.input_vel], [axis.encoder.vel_estimate]])
    vel_timer = ui.timer(0.05, vel_push)
    vel_check.bind_value_to(vel_plot.visible).bind_value_to(vel_timer.active)

with ui.row():
    for a, axis in enumerate([odrv.axis0, odrv.axis1]):
        with ui.card(), ui.column():
            axis_column(a, axis)
