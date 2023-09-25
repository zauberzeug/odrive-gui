from datetime import datetime
from typing import Any

from nicegui import ui
from odrive.pyfibre import fibre
from odrive.utils import dump_errors

MODES = {
    0: 'voltage',
    1: 'torque',
    2: 'velocity',
    3: 'position',
}

INPUT_MODES = {
    0: 'inactive',
    1: 'through',
    2: 'v-ramp',
    3: 'p-filter',
    5: 'trap traj',
    6: 't-ramp',
    7: 'mirror',
}

STATES = {
    0: 'undefined',
    1: 'idle',
    8: 'loop',
}


def controls(odrv) -> None:
    def reboot() -> None:
        try:
            odrv.reboot()
        except Exception as err:
            if type(err).__name__ == 'ObjectLostError':
                pass
            else:
                raise err

    with ui.row().classes('w-full justify-between items-center'):
        with ui.row():
            ui.label(f'SN {hex(odrv.serial_number).removeprefix("0x").upper()}')
            ui.label(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
            ui.label(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision} ' +
                     f'{"(dev)" if odrv.fw_version_unreleased else ""}')
            voltage = ui.label()
            ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
        with ui.row():
            ui.button(on_click=lambda: odrv.save_configuration()) \
                .props('icon=save flat round') \
                .tooltip('Save configuration')
            ui.button(on_click=lambda: dump_errors(odrv, hasattr(odrv, 'clear_errors'))) \
                .props('icon=bug_report flat round') \
                .tooltip('Dump and clear errors')
            ui.button(on_click=reboot) \
                .props('icon=restart_alt flat round') \
                .tooltip('Reboot odrive')

    with ui.row():
        for a, axis in enumerate([odrv.axis0, odrv.axis1]):
            if not axis.motor.is_calibrated:
                continue
            with ui.card(), ui.column():
                _create_axis_column(a, axis)


def _create_axis_column(index: int, axis: Any) -> None:
    ui.markdown(f'### Axis {index}')

    with ui.row().classes('w-full justify-between items-center'):
        power = ui.label()
        button = ui.button(on_click=lambda: axis.clear_errors()) \
            .props('icon=bug_report flat round').tooltip('Clear errors')
        button.set_visibility(hasattr(axis, 'clear_errors'))

    def update():
        if axis.__class__ == fibre.libfibre.EmptyInterface:
            return
        power.set_text(f'{axis.motor.current_control.Iq_measured * axis.motor.current_control.v_current_control_integral_q:.1f} W')
        button.set_enabled(axis.error != 0)

    ui.timer(0.1, update)

    ctr_cfg = axis.controller.config
    mtr_cfg = axis.motor.config
    enc_cfg = axis.encoder.config
    trp_cfg = axis.trap_traj.config

    with ui.row():
        mode = ui.toggle(MODES).bind_value(ctr_cfg, 'control_mode')
        ui.toggle(STATES) \
            .bind_value_to(axis, 'requested_state', forward=lambda x: x or 0) \
            .bind_value_from(axis, 'current_state')

    with ui.row():
        with ui.card().bind_visibility_from(mode, 'value', value=1):
            ui.markdown('**Torque**')
            torque = ui.number('input torque', value=0)
            def send_torque(sign: int) -> None: axis.controller.input_torque = sign * float(torque.value)
            with ui.row():
                ui.button(on_click=lambda: send_torque(-1)).props('round flat icon=remove')
                ui.button(on_click=lambda: send_torque(0)).props('round flat icon=radio_button_unchecked')
                ui.button(on_click=lambda: send_torque(1)).props('round flat icon=add')

        with ui.card().bind_visibility_from(mode, 'value', value=2):
            ui.markdown('**Velocity**')
            velocity = ui.number('input velocity', value=0)
            def send_velocity(sign: int) -> None: axis.controller.input_vel = sign * float(velocity.value)
            with ui.row():
                ui.button(on_click=lambda: send_velocity(-1)).props('round flat icon=fast_rewind')
                ui.button(on_click=lambda: send_velocity(0)).props('round flat icon=stop')
                ui.button(on_click=lambda: send_velocity(1)).props('round flat icon=fast_forward')

        with ui.card().bind_visibility_from(mode, 'value', value=3):
            ui.markdown('**Position**')
            position = ui.number('input position', value=0)
            def send_position(sign: int) -> None: axis.controller.input_pos = sign * float(position.value)
            with ui.row():
                ui.button(on_click=lambda: send_position(-1)).props('round flat icon=skip_previous')
                ui.button(on_click=lambda: send_position(0)).props('round flat icon=exposure_zero')
                ui.button(on_click=lambda: send_position(1)).props('round flat icon=skip_next')

        with ui.column():
            ui.number('pos_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'pos_gain')
            ui.number('vel_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_gain')
            ui.number('vel_integrator_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_integrator_gain')
            if hasattr(ctr_cfg, 'vel_differentiator_gain'):
                ui.number('vel_differentiator_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_differentiator_gain')

        with ui.column():
            ui.number('vel_limit', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_limit')
            ui.number('enc_bandwidth', format='%.3f').props('outlined').bind_value(enc_cfg, 'bandwidth')
            ui.number('current_lim', format='%.1f').props('outlined').bind_value(mtr_cfg, 'current_lim')
            ui.number('cur_bandwidth', format='%.3f').props('outlined').bind_value(mtr_cfg, 'current_control_bandwidth')
            ui.number('torque_lim', format='%.1f').props('outlined').bind_value(mtr_cfg, 'torque_lim')
            ui.number('requested_cur_range', format='%.1f').props('outlined').bind_value(mtr_cfg, 'requested_current_range')

    input_mode = ui.toggle(INPUT_MODES).bind_value(ctr_cfg, 'input_mode')
    with ui.row():
        ui.number('inertia', format='%.3f').props('outlined') \
            .bind_value(ctr_cfg, 'inertia') \
            .bind_visibility_from(input_mode, 'value', backward=lambda m: m in [2, 3, 5])
        ui.number('velocity ramp rate', format='%.3f').props('outlined') \
            .bind_value(ctr_cfg, 'vel_ramp_rate') \
            .bind_visibility_from(input_mode, 'value', value=2)
        ui.number('input filter bandwidth', format='%.3f').props('outlined') \
            .bind_value(ctr_cfg, 'input_filter_bandwidth') \
            .bind_visibility_from(input_mode, 'value', value=3)
        ui.number('trajectory velocity limit', format='%.3f').props('outlined') \
            .bind_value(trp_cfg, 'vel_limit') \
            .bind_visibility_from(input_mode, 'value', value=5)
        ui.number('trajectory acceleration limit', format='%.3f').props('outlined') \
            .bind_value(trp_cfg, 'accel_limit') \
            .bind_visibility_from(input_mode, 'value', value=5)
        ui.number('trajectory deceleration limit', format='%.3f').props('outlined') \
            .bind_value(trp_cfg, 'decel_limit') \
            .bind_visibility_from(input_mode, 'value', value=5)
        ui.number('torque ramp rate', format='%.3f').props('outlined') \
            .bind_value(ctr_cfg, 'torque_ramp_rate') \
            .bind_visibility_from(input_mode, 'value', value=6)
        ui.number('mirror ratio', format='%.3f').props('outlined') \
            .bind_value(ctr_cfg, 'mirror_ratio') \
            .bind_visibility_from(input_mode, 'value', value=7)
        ui.toggle({0: 'axis 0', 1: 'axis 1'}) \
            .bind_value(ctr_cfg, 'axis_to_mirror', forward=lambda x: 255 if x is None else x) \
            .bind_visibility_from(input_mode, 'value', value=7)

    def pos_push() -> None:
        pos_plot.push([datetime.now()], [[axis.controller.input_pos], [axis.encoder.pos_estimate]])
    pos_check = ui.checkbox('Position plot')
    pos_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_pos', 'pos_estimate'], loc='upper left', ncol=2)
    pos_timer = ui.timer(0.05, pos_push)
    pos_check.bind_value_to(pos_plot, 'visible').bind_value_to(pos_timer, 'active')

    def vel_push() -> None:
        vel_plot.push([datetime.now()], [[axis.controller.input_vel], [axis.encoder.vel_estimate]])
    vel_check = ui.checkbox('Velocity plot')
    vel_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_vel', 'vel_estimate'], loc='upper left', ncol=2)
    vel_timer = ui.timer(0.05, vel_push)
    vel_check.bind_value_to(vel_plot, 'visible').bind_value_to(vel_timer, 'active')

    def id_push() -> None:
        id_plot.push([datetime.now()], [[axis.motor.current_control.Id_setpoint], [axis.motor.current_control.Id_measured]])
    id_check = ui.checkbox('Id plot')
    id_plot = ui.line_plot(n=2, update_every=10).with_legend(['Id_setpoint', 'Id_measured'], loc='upper left', ncol=2)
    id_timer = ui.timer(0.05, id_push)
    id_check.bind_value_to(id_plot, 'visible').bind_value_to(id_timer, 'active')

    def iq_push() -> None:
        iq_plot.push([datetime.now()], [[axis.motor.current_control.Iq_setpoint], [axis.motor.current_control.Iq_measured]])
    iq_check = ui.checkbox('Iq plot')
    iq_plot = ui.line_plot(n=2, update_every=10).with_legend(['Iq_setpoint', 'Iq_measured'], loc='upper left', ncol=2)
    iq_timer = ui.timer(0.05, iq_push)
    iq_check.bind_value_to(iq_plot, 'visible').bind_value_to(iq_timer, 'active')

    def t_push() -> None:
        t_plot.push([datetime.now()], [[axis.motor.fet_thermistor.temperature]])
    t_check = ui.checkbox('Temperature plot')
    t_plot = ui.line_plot(n=1, update_every=10)
    t_timer = ui.timer(0.05, t_push)
    t_check.bind_value_to(t_plot, 'visible').bind_value_to(t_timer, 'active')
