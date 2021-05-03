#!/usr/bin/env python3
import streamlit as st
import odrive
from odrive.utils import dump_errors
import numpy as np
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
    view.vel = max(
        abs(odrv.axis0.controller.input_vel),
        abs(odrv.axis1.controller.input_vel),
    )

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

        if oh.modes[view_axis.controller.config.control_mode] == 'velocity control':
            view.vel = st.number_input(f'input_vel: {view_axis.controller.input_vel}', min_value=0.0, value=view.vel, key=f'vel-{a}')
            if abs(view.vel) != abs(view_axis.controller.input_vel):
                view_axis.controller.input_vel = odrv_axis.controller.input_vel = view.vel * np.sign(view_axis.controller.input_vel)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}', -view.vel)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}', 0.0)
            oh.setbutton(odrv_axis, view_axis, f'controller.input_vel {a}', view.vel)

        view_axis.requested_state = view_axis.current_state
        oh.selectbox(odrv_axis, view_axis, f'requested_state {a}', oh.states)
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
