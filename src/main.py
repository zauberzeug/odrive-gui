#!/usr/bin/env python3
import streamlit as st
import odrive
from odrive.utils import dump_errors
import numpy as np
import pylab as pl
import session
import time
import threading
import odrive_helpers as oh


st.title("ODrive Tuning & Debugging")

@st.cache(allow_output_mutation=True)
def get_odrv():
    return odrive.find_any()

odrv = get_odrv()

view = session.get_state()
if view.vbus_voltage is None:
    hashable = oh.make_hashable(odrv, 'odrv')
    for key in dir(hashable):
        if not key.startswith('_'):
            setattr(view, key, getattr(hashable, key))
    view.torque = [
        abs(odrv.axis0.controller.input_torque),
        abs(odrv.axis1.controller.input_torque),
    ]
    view.vel = [
        abs(odrv.axis0.controller.input_vel),
        abs(odrv.axis1.controller.input_vel),
    ]
    view.pos = [
        abs(odrv.axis0.controller.input_pos),
        abs(odrv.axis1.controller.input_pos),
    ]

def update():

    print('start thread', threading.current_thread().name)
    while threading.current_thread() == [ t for t in threading.enumerate() if t.name.startswith('update') ][-1]:
        t0 = time.time()
        while time.time() < t0 + 1.0:
            for key, value in view.data.items():
                value.append(oh.rgetattr(odrv, key))
            time.sleep(0.02)
        for key in view.data:
            view.data[key] = view.data[key][-500:]
        view.sync()
    print('stop thread', threading.current_thread().name)

if view.data is None:
    keys = [
        'axis0.encoder.pos_estimate',
        'axis1.encoder.pos_estimate',
        'axis0.controller.input_pos',
        'axis1.controller.input_pos',
        'axis0.encoder.vel_estimate',
        'axis1.encoder.vel_estimate',
        'axis0.controller.input_vel',
        'axis1.controller.input_vel',
    ]
    view.data = { key: [] for key in keys }
    thread = threading.Thread(target=update, daemon=True, name='update_%.3f' % time.time())
    thread.start()

cols = st.beta_columns(2)

for a in range(2):

    view_axis = view.axis0 if a == 0 else view.axis1
    odrv_axis = odrv.axis0 if a == 0 else odrv.axis1

    with cols[a]:

        st.header(f'Axis {a}')

        if odrv_axis.error:
            st.write('Error:', hex(odrv_axis.error))

        st.subheader('Settings')

        oh.number_input(odrv_axis, view_axis, f'controller.config.pos_gain {a}', min_value=0.0)
        oh.number_input(odrv_axis, view_axis, f'controller.config.vel_gain {a}', min_value=0.0)
        oh.number_input(odrv_axis, view_axis, f'controller.config.vel_integrator_gain {a}', min_value=0.0)
        oh.number_input(odrv_axis, view_axis, f'controller.config.vel_limit {a}', min_value=0.0)
        oh.number_input(odrv_axis, view_axis, f'encoder.config.bandwidth {a}', min_value=0.0)

        st.subheader('Test')

        oh.radio(odrv_axis, view_axis, f'controller.config.control_mode {a}', oh.modes)

        if oh.modes[view_axis.controller.config.control_mode] == 'torque control':

            view.torque[a] = st.number_input(f'input_torque: {view_axis.controller.input_torque}', value=view.torque[a], key=f'torque-{a}')
            if abs(view.torque[a]) != abs(view_axis.controller.input_torque):
                view_axis.controller.input_torque = odrv_axis.controller.input_torque = view.torque[a] * np.sign(view_axis.controller.input_torque)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_torque {a}0', -view.torque[a])
            oh.setbutton(odrv_axis, view_axis, f'controller.input_torque {a}1', 0.0)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_torque {a}2', view.torque[a])

        if oh.modes[view_axis.controller.config.control_mode] == 'position control':

            view.pos[a] = st.number_input(f'input_pos: {view_axis.controller.input_pos}', value=view.pos[a], key=f'pos-{a}')
            if abs(view.pos[a]) != abs(view_axis.controller.input_pos):
                view_axis.controller.input_pos = odrv_axis.controller.input_pos = view.pos[a] * np.sign(view_axis.controller.input_pos)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_pos {a}0', -view.pos[a])
            oh.setbutton(odrv_axis, view_axis, f'controller.input_pos {a}1', 0.0)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_pos {a}2', view.pos[a])

            fig, ax = pl.subplots()
            pl.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
            ax.set_title('position')
            ax.plot(view.data[f'axis{a}.encoder.pos_estimate'])
            ax.plot(view.data[f'axis{a}.controller.input_pos'])
            st.pyplot(fig)

        if oh.modes[view_axis.controller.config.control_mode] == 'velocity control':

            view.vel[a] = st.number_input(f'input_vel: {view_axis.controller.input_vel}', min_value=0.0, value=view.vel[a], key=f'vel-{a}')
            if abs(view.vel[a]) != abs(view_axis.controller.input_vel):
                view_axis.controller.input_vel = odrv_axis.controller.input_vel = view.vel[a] * np.sign(view_axis.controller.input_vel)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}0', -view.vel[a])
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}1', 0.0)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}2', view.vel[a])

            fig, ax = pl.subplots()
            pl.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
            ax.set_title('velocity')
            ax.plot(view.data[f'axis{a}.encoder.vel_estimate'])
            ax.plot(view.data[f'axis{a}.controller.input_vel'])
            st.pyplot(fig)

        view_axis.current_state = oh.states.index(st.selectbox('state', oh.states, view_axis.current_state, key=f'state-{a}'))
        if view_axis.current_state != odrv_axis.current_state:
            odrv_axis.requested_state = view_axis.current_state

        for state in ['idle', 'closed loop control']:
            if oh.states[view_axis.current_state] != state:
                if st.button(f'Switch to "{state}" state', key=f'button-{state}-{a}'):
                    view_axis.current_state = oh.states.index(state)

st.sidebar.header('ODrive')

st.sidebar.write('Serial number:', hex(odrv.serial_number).removeprefix('0x').upper())
st.sidebar.write('Hardware version:', f'{odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
st.sidebar.write('Firmware version:', f'{odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision}', '(dev)' if odrv.fw_version_unreleased else '')
st.sidebar.write('Voltage:', np.round(odrv.vbus_voltage, 2))

if st.sidebar.button('Clear errors'):
    dump_errors(odrv, True)

if st.sidebar.button('Save configuration'):
    odrv.save_configuration()

if st.sidebar.button('Reboot'):
    odrv.reboot()

view.sync()
