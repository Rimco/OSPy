#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

# System imports
from datetime import datetime, date
from threading import Timer
import logging
import shelve
import shutil
import threading

from . import helpers
import traceback
import os
import time
from functools import reduce

OPTIONS_FILE = './ospy/data/default/options.db'
OPTIONS_TMP = './ospy/data/tmp/options.db'
OPTIONS_BACKUP = './ospy/data/backup/options.db'

class _Options(object):
    # Using an array to preserve order
    OPTIONS = [
        #######################################################################
        # System ##############################################################
        {
            "key": "name",
            "name": "System name",
            "default": "OpenSprinkler Pi",
            "help": "Unique name of this OpenSprinkler system.",
            "category": "System"
        },
        {
            "key": "theme",
            "name": "System theme",
            "default": "basic",
            "options": helpers.themes,
            "help": "Determines the look of the GUI.",
            "category": "System"
        },
        {
            "key": "location",
            "name": "Location",
            "default": "",
            "help": "City name or zip code. Used to determine location via OpenStreetMap for weather information.",
            "category": "System"
        },
        {
            "key": "stormglass_key",
            "name": "Storm Glass API key",
            "default": "",
            "help": "To make use of local weather conditions, a Storm Glass API key is needed.",
            "category": "System"
        },
        {
            "key": "time_format",
            "name": "24-hour clock",
            "default": True,
            "help": "Display times in 24 hour format (as opposed to AM/PM style.)",
            "category": "System"
        },
        {
            "key": "web_port",
            "name": "HTTP port",
            "default": 8080,
            "help": "HTTP port (effective after reboot.)",
            "category": "System",
            "min": 1,
            "max": 65535
        },
        {
            "key": "enabled_plugins",
            "name": "Enabled plug-ins",
            "default": []
        },
        {
            "key": "plugin_status",
            "name": "Plug-in status",
            "default": {}
        },
        {
            "key": "auto_plugin_update",
            "name": "Automatic plug-in updates",
            "default": True
        },

        #######################################################################
        # Security ############################################################
        {
            "key": "no_password",
            "name": "Disable security",
            "default": False,
            "help": "Allow anonymous users to access the system without a password.",
            "category": "Security"
        },

        #######################################################################
        # Station Handling ####################################################
        {
            "key": "max_usage",
            "name": "Maximum usage",
            "default": 1.0,
            "help": "Determines how schedules of different stations are combined. "
                    "0 is no limit. 1 is sequential in case all stations have a usage of 1.",
            "category": "Station Handling"
        },
        {
            "key": "output_count",
            "name": "Number of outputs",
            "default": 8,
            "help": "The number of outputs available (8 + 8*extensions)",
            "category": "Station Handling",
            "min": 8,
            "max": 1000
        },
        {
            "key": "station_delay",
            "name": "Station delay",
            "default": 0,
            "help": "Station delay time (in seconds), between 0 and 3600.",
            "category": "Station Handling",
            "min": 0,
            "max": 3600
        },
        {
            "key": "min_runtime",
            "name": "Minimum runtime",
            "default": 0,
            "help": "Skip the station delay if the run time was less than this value (in seconds), between 0 and 86400.",
            "category": "Station Handling",
            "min": 0,
            "max": 86400
        },

        #######################################################################
        # Configure Master ####################################################
        {
            "key": "master_relay",
            "name": "Activate relay",
            "default": False,
            "help": "Also activate the relay as master output.",
            "category": "Configure Master"
        },
        {
            "key": "master_on_delay",
            "name": "Master on delay",
            "default": 0,
            "help": "Master on delay (in seconds), between -1800 and +1800.",
            "category": "Configure Master",
            "min": -1800,
            "max": +1800
        },
        {
            "key": "master_off_delay",
            "name": "Master off delay",
            "default": 0,
            "help": "Master off delay (in seconds), between -1800 and +1800.",
            "category": "Configure Master",
            "min": -1800,
            "max": +1800
        },

        #######################################################################
        # Rain Sensor #########################################################
        {
            "key": "rain_sensor_enabled",
            "name": "Use rain sensor",
            "default": False,
            "help": "Use rain sensor.",
            "category": "Rain Sensor"
        },
        {
            "key": "rain_sensor_no",
            "name": "Normally open",
            "default": True,
            "help": "Rain sensor default.",
            "category": "Rain Sensor"
        },

        #######################################################################
        # Pressure Sensor #####################################################
        {
            "key": "pressure_sensor_analog",
            "name": "Use analog pressure sensor",
            "default": False,
            "help": "Use an analog pressure sensor connected to PCF8591 via I2C.",
            "category": "Pressure Sensor"
        },
        {
            "key": "pressure_sensor_analog_channel",
            "name": "Analog channel",
            "default": 1,
            "help": "The PCF8591 channel to which the pressure sensor is connected.",
            "category": "Pressure Sensor",
            "min": 0,
            "max": 3
        },
        {
            "key": "pressure_sensor_analog_conversion",
            "name": "Voltage conversion",
            "default": "(v - 0.5) * 3.0",
            "help": "The formula to use to convert the analog voltage (v) into bar.",
            "category": "Pressure Sensor"
        },

        #######################################################################
        # Logging #############################################################
        {
            "key": "run_log",
            "name": "Enable run log",
            "default": False,
            "help": "Log all runs - note that repetitive writing to an SD card can shorten its lifespan.",
            "category": "Logging"
        },
        {
            "key": "run_entries",
            "name": "Max run entries",
            "default": 100,
            "help": "Number of run entries to save to disk, 0=no limit.",
            "category": "Logging",
            "min": 0,
            "max": 1000
        },
        {
            "key": "debug_log",
            "name": "Enable debug log",
            "default": False,
            "help": "Log all internal events (for debugging purposes).",
            "category": "Logging"
        },


        #######################################################################
        # Not in Options page as-is ###########################################
        {
            "key": "scheduler_enabled",
            "name": "Enable scheduler",
            "default": True,
        },
        {
            "key": "manual_mode",
            "name": "Manual operation",
            "default": False,
        },
        {
            "key": "level_adjustment",
            "name": "Level adjustment set by the user (fraction)",
            "default": 1.0,
        },
        {
            "key": "rain_block",
            "name": "Rain block (rain delay) set by the user (datetime)",
            "default": datetime(1970, 1, 1),
        },
        {
            "key": "temp_unit",
            "name": "C/F",
            "default": 'C',
        },

        {
            "key": "password_hash",
            "name": "Current password hash",
            "default": "opendoor",
        },
        {
            "key": "password_salt",
            "name": "Current password salt",
            "default": "",
        },
        {
            "key": "password_time",
            "name": "Current password decryption time",
            "default": 0,
        },
        {
            "key": "logged_runs",
            "name": "The runs that have been logged",
            "default": []
        },
        {
            "key": "weather_cache",
            "name": "ETo and rain value cache",
            "default": {}
        },
        {
            "key": "last_save",
            "name": "Timestamp of the last database save",
            "default": time.time()
        }
    ]

    def __init__(self):
        self._values = {}
        self._write_timer = None
        self._callbacks = {}
        self._block = []
        self._lock = threading.Lock()

        for info in self.OPTIONS:
            self._values[info["key"]] = info["default"]

        # UPGRADE from v2 (does not delete old files):
        if not os.path.isdir(os.path.dirname(OPTIONS_FILE)):
            helpers.mkdir_p(os.path.dirname(OPTIONS_FILE))
            for old_options in ['./ospy/data/options.db', './ospy/data/options.db.dat', './ospy/data/options.db.bak', './ospy/data/options.db.tmp']:
                if os.path.isfile(old_options):
                    shutil.copy(old_options, OPTIONS_FILE)
                    break

        for options_file in [OPTIONS_FILE, OPTIONS_TMP, OPTIONS_BACKUP]:
            try:
                if os.path.isdir(os.path.dirname(options_file)):
                    db = shelve.open(options_file)
                    if list(db.keys()):
                        self._values.update(self._convert_str_to_datetime(db))
                        db.close()
                        break
                    else:
                        db.close()
            except Exception as err:
                pass

        if not self.password_salt:  # Password is not hashed yet
            self.password_salt = helpers.password_salt()
            self.password_hash = helpers.password_hash(self.password_hash, self.password_salt)

    def __del__(self):
        if self._write_timer is not None:
            self._write_timer.cancel()

    def add_callback(self, key, function):
        if key not in self._callbacks:
            self._callbacks[key] = {
                'last_value': getattr(self, key),
                'functions': []
            }

        if function not in self._callbacks[key]['functions']:
            self._callbacks[key]['functions'].append(function)

    def remove_callback(self, key, function):
        if key in self._callbacks:
            if function in self._callbacks[key]['functions']:
                self._callbacks[key]['functions'].remove(function)

    def __str__(self):
        import pprint

        pp = pprint.PrettyPrinter(indent=2)
        return pp.pformat(self._values)

    def __getattr__(self, item):
        if item.startswith('_'):
            result = super(_Options, self).__getattribute__(item)
        elif item not in self._values:
            raise AttributeError
        else:
            result = self._values[item]
        return result

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(_Options, self).__setattr__(key, value)
        else:
            self._values[key] = value

            if key in self._callbacks:
                if value != self._callbacks[key]['last_value']:
                    for cb in self._callbacks[key]['functions']:
                        try:
                            cb(key, self._callbacks[key]['last_value'], value)
                        except Exception:
                            logging.error('Callback failed:\n' + traceback.format_exc())
                    self._callbacks[key]['last_value'] = value

            # Only write after 1 second without any more changes
            if self._write_timer is not None:
                self._write_timer.cancel()
            self._write_timer = Timer(1.0, self._write)
            self._write_timer.start()

    def __delattr__(self, item):
        if item.startswith('_'):
            super(_Options, self).__delattr__(item)
        else:
            del self._values[item]

            # Only write after 1 second without any more changes
            if self._write_timer is not None:
                self._write_timer.cancel()
            self._write_timer = Timer(1.0, self._write)
            self._write_timer.start()

    # Makes it possible to use this class like options[<item>]
    __getitem__ = __getattr__

    # Makes it possible to use this class like options[<item>] = <value>
    __setitem__ = __setattr__

    # Makes it possible to use this class like del options[<item>]
    __delitem__ = __delattr__

    def __contains__(self, item):
        return item in self._values

    def _convert_datetime_to_str(self, inp):
        if isinstance(inp, dict):
            result = {}
            for k in inp:
                result[self._convert_datetime_to_str(k)] = self._convert_datetime_to_str(inp[k])
        elif isinstance(inp, list):
            result = []
            for v in inp:
                result.append(self._convert_datetime_to_str(v))
        elif isinstance(inp, datetime):
            result = 'DATETIME:' + inp.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(inp, date):
            result = 'DATE:' + inp.strftime('%Y-%m-%d')
        else:
            result = inp
        return result

    def _convert_str_to_datetime(self, inp):
        if isinstance(inp, dict) or isinstance(inp, shelve.Shelf):
            result = {}
            for k in inp:
                result[self._convert_str_to_datetime(k)] = self._convert_str_to_datetime(inp[k])
        elif isinstance(inp, list):
            result = []
            for v in inp:
                result.append(self._convert_str_to_datetime(v))
        elif isinstance(inp, str) and inp.startswith('DATETIME:'):
            result = datetime.strptime(inp[9:], '%Y-%m-%d %H:%M:%S')
        elif isinstance(inp, str) and inp.startswith('DATE:'):
            result = datetime.strptime(inp[5:15], '%Y-%m-%d').date()
        else:
            result = inp
        return result

    def _write(self):
        """This function saves the current data to disk. Use a timer to limit the call rate."""
        try:
            with self._lock:
                logging.debug('Saving options to disk')

                options_dir = os.path.dirname(OPTIONS_FILE)
                tmp_dir = os.path.dirname(OPTIONS_TMP)
                backup_dir = os.path.dirname(OPTIONS_BACKUP)

                if os.path.isdir(tmp_dir):
                    shutil.rmtree(tmp_dir)
                helpers.mkdir_p(tmp_dir)

                if helpers.is_python2():
                    from dumbdbm import open as dumb_open
                else:
                    from dbm.dumb import open as dumb_open

                db = shelve.Shelf(dumb_open(OPTIONS_TMP))
                db.clear()
                if helpers.is_python2():
                    # We need to make sure that datetime objects are readable in Python 3
                    # This conversion takes care of that as long as we run at least once in Python 2
                    db.update(self._convert_datetime_to_str(self._values))
                else:
                    db.update(self._values)

                db.close()

                remove_backup = True
                try:
                    db = shelve.open(OPTIONS_BACKUP)
                    if time.time() - db['last_save'] < 3600:
                        remove_backup = False
                    db.close()
                except Exception:
                    pass
                del db

                if os.path.isdir(backup_dir) and remove_backup:
                    for i in range(10):
                        try:
                            shutil.rmtree(backup_dir)
                            break
                        except Exception:
                            time.sleep(0.2)
                    else:
                        shutil.rmtree(backup_dir)

                if os.path.isdir(options_dir):
                    if not os.path.isdir(backup_dir):
                        shutil.move(options_dir, backup_dir)
                    else:
                        for i in range(10):
                            try:
                                shutil.rmtree(options_dir)
                                break
                            except Exception:
                                time.sleep(0.2)
                        else:
                            shutil.rmtree(options_dir)

                shutil.move(tmp_dir, options_dir)

                if helpers.is_python2():
                    from whichdb import whichdb
                else:
                    from dbm import whichdb

                logging.debug('Saved db as %s', whichdb(OPTIONS_FILE))
        except Exception:
            logging.warning('Saving error:\n' + traceback.format_exc())

    def get_categories(self):
        result = []
        for info in self.OPTIONS:
            if "category" in info and info["category"] not in result:
                result.append(info["category"])
        return result

    def get_options(self, category=None):
        if category is None:
            result = [opt["key"] for opt in self.OPTIONS]
        else:
            result = []
            for info in self.OPTIONS:
                if "category" in info and info["category"] == category:
                    result.append(info["key"])
        return result

    def get_info(self, option):
        return self.OPTIONS[option]

    @staticmethod
    def cls_name(obj, key=""):
        tpy = (obj if isinstance(obj, type) else type(obj))
        return 'Cls_' + tpy.__module__ + '_' + tpy.__name__ + '_' + str(key).replace(' ', '_')

    def load(self, obj, key=""):
        cls = self.cls_name(obj, key)
        self._block.append(cls)
        try:
            values = getattr(self, cls)
            for name, value in values.items():
                setattr(obj, name, value)
        except AttributeError:
            pass
        self._block.remove(cls)

    def save(self, obj, key=""):
        cls = self.cls_name(obj, key)
        if cls not in self._block:
            values = {}
            exclude = obj.SAVE_EXCLUDE if hasattr(obj, 'SAVE_EXCLUDE') else []
            for attr in [att for att in dir(obj) if not att.startswith('_') and att not in exclude]:
                if not hasattr(getattr(obj, attr), '__call__'):
                    values[attr] = getattr(obj, attr)

            setattr(self, cls, values)

    def erase(self, obj, key=""):
        cls = self.cls_name(obj, key)
        if hasattr(self, cls):
            delattr(self, cls)

    def available(self, obj, key=""):
        cls = self.cls_name(obj, key)
        return hasattr(self, cls)

options = _Options()


class _LevelAdjustments(dict):
    def __init__(self):
        super(_LevelAdjustments, self).__init__()

    def total_adjustment(self):
        return max(0.0, min(5.0, reduce(lambda x, y: x * y, list(self.values()), options.level_adjustment)))

level_adjustments = _LevelAdjustments()


class _RainBlocks(dict):
    def __init__(self):
        super(_RainBlocks, self).__init__()

    def block_end(self):
        return max(list(self.values()) + [options.rain_block])

    def seconds_left(self):
        return max(0, (self.block_end() - datetime.now()).total_seconds())

rain_blocks = _RainBlocks()
