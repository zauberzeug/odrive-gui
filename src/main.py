#!/usr/bin/env python3
import streamlit as st
import odrive
from odrive.utils import dump_errors
import numpy as np
import session
import time
import threading
from odrive_helpers import make_hashable, states, modes

st.title("ODrive Tuning & Debugging")

@st.cache(allow_output_mutation=True)
def get_odrv():
    return odrive.find_any()

odrv = get_odrv()

view = session.get_state()
if view.vbus_voltage is None:
    hashable = make_hashable(odrv)
    for key in dir(hashable):
        if not key.startswith('_'):
            setattr(view, key, getattr(hashable, key))
    view.vel = max(
        abs(odrv.axis0.controller.input_vel),
        abs(odrv.axis1.controller.input_vel),
    )

cols = st.beta_columns(2)

for a, axis in enumerate([odrv.axis0, odrv.axis1]):

    view_axis = view.axis0 if a == 0 else view.axis1
    view_controller = view_axis.controller
    view_config = view_controller.config
    odrv_config = axis.controller.config

    with cols[a]:

        st.header(f'Axis {a}')

        if axis.error:
            st.write('Error:', hex(axis.error))

        st.subheader('Settings')

        view_config.pos_gain = odrv_config.pos_gain = st.number_input('pos_gain', min_value=0.0, value=odrv_config.pos_gain, key=f'number-pos_gain-{a}')
        view_config.vel_gain = odrv_config.vel_gain = st.number_input('vel_gain', min_value=0.0, value=odrv_config.vel_gain, key=f'number-vel_gain-{a}')
        view_config.vel_integrator = odrv_config.vel_integrator_gain = st.number_input('vel_integrator_gain', min_value=0.0, value=odrv_config.vel_integrator_gain, key=f'number-vel_integrator_gain-{a}')
        view_config.vel_limit = odrv_config.vel_limit = st.number_input('vel_limit', min_value=0.0, value=odrv_config.vel_limit, key=f'number-vel_limit-{a}')

        st.subheader('Test')

        view_config.control_mode = odrv_config.control_mode = modes.index(st.radio('Mode', modes, odrv_config.control_mode, key=f'selectbox-mode-{a}'))

        if modes[view_config.control_mode] == 'velocity control':
            st.write('input_vel:', view_controller.input_vel)
            view.vel = st.number_input('new value', min_value=0.0, value=view.vel, key=f'number-vel-{a}')
            if st.button(f'Set input_vel = {-view.vel}', key=f'button-vel-{a}a'):
                view_controller.input_vel = axis.controller.input_vel = -view.vel
            if st.button('Set input_vel = 0.0', key=f'button-vel-{a}b'):
                view_controller.input_vel = axis.controller.input_vel = 0.0
            if st.button(f'Set input_vel = {view.vel}', key=f'button-vel-{a}c'):
                view_controller.input_vel = axis.controller.input_vel = view.vel

        view_axis.current_state = axis.requested_state = states.index(st.selectbox('State', states, view_axis.current_state, key=f'selectbox-state-{a}'))
        for state in ['idle', 'closed loop control']:
            if states[view_axis.current_state] != state:
                if st.button(f'Switch to "{state}" state', key=f'button-{state}-{a}'):
                    view_axis.current_state = states.index(state)

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

def update():

    print('start thread', threading.current_thread().name)
    while threading.current_thread() == [ t for t in threading.enumerate() if t.name.startswith('update') ][-1]:
        t0 = time.time()
        while time.time() < t0 + 1.0:
            view.data['vbus'].append(odrv.vbus_voltage)
            time.sleep(0.1)
        view.data['time'] = time.time()
        view.data['vbus'] = view.data['vbus'][-20:]
        view.sync()
    print('stop thread', threading.current_thread().name)

if view.data is None:
    view.data = {
        'time': 0,
        'vbus': [],
    }
    thread = threading.Thread(target=update, daemon=True, name='update_%.3f' % time.time())
    thread.start()

st.sidebar.json(view.data)

view.sync()
