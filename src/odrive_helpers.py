#!/usr/bin/env python3
import fibre

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

