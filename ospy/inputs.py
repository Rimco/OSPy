#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

import logging

class _RainSensorMixIn(object):
    def rain_sensed(self):
        from ospy.options import options
        return options.rain_sensor_enabled and (options.rain_sensor_no == self.rain_input)


class _DummyInputs(_RainSensorMixIn):
    def __init__(self):
        self.rain_input = False

    def get_water_pressure(self):
        from math import nan
        return nan

class _IOInputs(_RainSensorMixIn):
    def __init__(self):
        self._mapping = {}
        self._initialized = False

    def __getattr__(self, item):
        if not self._initialized:
            self._initialized = True
            for pin in list(self._mapping.values()):
                self._io.setup(pin, self._io.IN)

        if item.startswith('_'):
            return super(_IOInputs, self).__getattribute__(item)
        else:
            return self._io.input(self._mapping[item])


class _RPiInputs(_IOInputs, _RainSensorMixIn):
    def __init__(self):
        import RPi.GPIO as GPIO  # RPi hardware

        super(_RPiInputs, self).__init__()
        self._io = GPIO
        self._io.setwarnings(False)
        self._io.setmode(self._io.BOARD)

        self._mapping = {
            'rain_input': 8
        }

        self._smbus = None

    def _channel_change(self, key, old, new):
        self._smbus.write_byte(0x48, new)

    def get_water_pressure(self):
        from ospy.options import options
        from math import nan
        if options.pressure_sensor_analog:
            try:
                if self._smbus is None:
                    from smbus import SMBus
                    self._smbus = SMBus(1)
                    options.add_callback('pressure_sensor_analog_channel', self._channel_change)
                    self._smbus.write_byte(0x48, options.pressure_sensor_analog_channel)

                v = self._smbus.read_byte(0x48)*3.3/255
                return round(max(0.0, eval(options.pressure_sensor_analog_conversion)), 1)
            except Exception as err:
                logging.debug(err)
                return nan
        else:
            return nan

class _BBBInputs(_IOInputs, _RainSensorMixIn):
    def __init__(self):
        import Adafruit_BBIO.GPIO as GPIO  # Beagle Bone Black hardware

        super(_BBBInputs, self).__init__()
        self._io = GPIO
        self._io.setwarnings(False)

        self._mapping = {
            'rain_input': "P9_15"
        }

    def get_water_pressure(self):
        from math import nan
        return nan

try:
    inputs = _RPiInputs()
except Exception:
    try:
        inputs = _BBBInputs()
    except Exception:
        inputs = _DummyInputs()