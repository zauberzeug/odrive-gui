#!/usr/bin/env python3
import streamlit as st
import fibre
import functools

def make_hashable(obj, name=''):

    d = {}
    for key, value in obj._remote_attributes.items():
        if type(value) == fibre.remote_object.RemoteObject:
            d[key] = make_hashable(value, key)
        if type(value) == fibre.remote_object.RemoteProperty:
            d[key] = value.get_value()

    return type(name, (), d)()

states = [
    'undefined',
    'idle',
    'startup sequence',
    'full calibration sequence',
    'motor calibration',
    'sensorless control',
    'encoder index search',
    'encoder offset calibration',
    'closed loop control',
    'lockin spin',
    'encoder dir find',
    'homing',
]

modes = [
    'voltage control',
    'torque control',
    'velocity control',
    'position control',
]

# https://stackoverflow.com/a/31174427/3419103
def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)
def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return functools.reduce(_getattr, [obj] + attr.split('.'))

def number_input(odrv, view, id_, **kwargs):

    path = id_.split()[0]
    value = rgetattr(view, path)
    name = path.replace('config.', '').replace('.', ': ')
    result = st.number_input(name, value=value, key=id_.replace(' ', '-'), **kwargs)
    if result != rgetattr(odrv, path):
        rsetattr(odrv, path, result)
    rsetattr(view, path, result)

def radio(odrv, view, id_, options):

    path = id_.split()[0]
    value = rgetattr(view, path)
    name = path.replace('config.', '').replace('.', ': ')
    result = options.index(st.radio(name, options, value, key=id_.replace(' ', '-')))
    if result != rgetattr(odrv, path):
        print(path, result)
        rsetattr(odrv, path, result)
    rsetattr(view, path, result)

def setbutton(odrv, view, id_, value):

    path = id_.split()[0]
    name = path.replace('config.', '').replace('.', ': ')
    if st.button(f'{name} := {value}', key=id_.replace(' ', '-')):
        rsetattr(odrv, path, value)
        rsetattr(view, path, value)

