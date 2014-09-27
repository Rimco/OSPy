#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

# System imports
from threading import Thread
import datetime
import logging
import os
import random
import subprocess
import time

# Local imports
from web import form
from web.session import sha1
import web


def determine_platform():
    try:
        import RPi.GPIO
        return 'pi'
    except Exception:
        pass
    try:
        import Adafruit_BBIO.GPIO
        return 'bo'
    except Exception:
        pass
    return ''


def get_rpi_revision():
    try:
        import RPi.GPIO as GPIO
        return GPIO.RPI_REVISION
    except ImportError:
        return 0


def reboot(wait=1, block=False):
    if block:
        from stations import stations
        stations.clear()
        time.sleep(wait)
        logging.info("Rebooting...")
        subprocess.Popen(['reboot'])
    else:
        t = Thread(target=reboot, args=(wait, True))
        t.start()


def poweroff(wait=1, block=False):
    if block:
        from stations import stations
        stations.clear()
        time.sleep(wait)
        logging.info("Powering off...")
        subprocess.Popen(['poweroff'])
    else:
        t = Thread(target=poweroff, args=(wait, True))
        t.start()


def restart(wait=1, block=False):
    if block:
        from stations import stations
        stations.clear()
        time.sleep(wait)
        logging.info("Restarting...")
        subprocess.Popen('service ospy restart'.split())
    else:
        t = Thread(target=restart, args=(wait, True))
        t.start()


def uptime():
    """Returns UpTime for RPi"""
    try:
        with open("/proc/uptime") as f:
            total_sec = float(f.read().split()[0])
            string = str(datetime.timedelta(seconds=total_sec)).split('.')[0]
    except Exception:
        string = 'Uptime unavailable'

    return string


def get_ip():
    """Returns the IP adress if available."""
    try:
        arg = 'ip route list'
        p = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
        data = p.communicate()
        split_data = data[0].split()
        ipaddr = split_data[split_data.index('src') + 1]
        return ipaddr
    except Exception:
        return "No IP Settings"


def get_cpu_temp(unit=None):
    """Returns the temperature of the CPU if available."""
    try:
        platform = determine_platform()
        if platform == 'bo':
            res = os.popen('cat /sys/class/hwmon/hwmon0/device/temp1_input').readline()
            temp = str(int(float(res) / 1000))
        elif platform == 'pi':
            res = os.popen('vcgencmd measure_temp').readline()
            temp = res.replace("temp=", "").replace("'C\n", "")
        else:
            temp = str(0)

        if unit == 'F':
            return str(9.0 / 5.0 * float(temp) + 32)
        elif unit is not None:
            return str(float(temp))
        else:
            return temp
    except Exception:
        return '!!'


def timestr(t):
    return str((t / 60 >> 0) / 10 >> 0) + str((t / 60 >> 0) % 10) + ":" + str((t % 60 >> 0) / 10 >> 0) + str(
        (t % 60 >> 0) % 10)


def stop_onrain():
    """Stop stations that do not ignore rain."""
    from stations import stations
    for station in stations.get():
        if not station.ignore_rain:
            station.activated = False


def save_to_options(qdict):
    from options import options
    from stations import stations

    for option in options.OPTIONS:
        key = option['key']
        if 'category' in option:
            if key in qdict:
                value = qdict[key]
                if isinstance(option['default'], bool):
                    options[key] = True if value and value != "off" else False
                elif isinstance(option['default'], int):
                    if 'min' in option and int(qdict[key]) < option['min']:
                        continue
                    if 'max' in option and int(qdict[key]) > option['max']:
                        continue
                    options[key] = int(qdict[key])
                else:
                    options[key] = qdict[key]
            else:
                if isinstance(option['default'], bool):
                    options[key] = False

    if 'master' in qdict:
        m = int(qdict['master'])
        if m < 0:
            stations.master = None
        elif m < stations.count():
            stations.master = m

    if 'old_password' in qdict and qdict['old_password'] != "":
        try:
            if test_password(qdict['old_password']):
                if qdict['new_password'] == "":
                    raise web.seeother('/options?errorCode=pw_blank')
                elif qdict['new_password'] == qdict['check_password']:
                    options.password_salt = password_salt()  # Make a new salt
                    options.password_hash = password_hash(qdict['new_password'], options.password_salt)
                else:
                    raise web.seeother('/options?errorCode=pw_mismatch')
            else:
                raise web.seeother('/options?errorCode=pw_wrong')
        except KeyError:
            pass


########################
#### Login Handling ####

def password_salt():
    return "".join(chr(random.randint(33, 127)) for _ in xrange(64))


def password_hash(password, salt):
    return sha1(password + salt).hexdigest()


def test_password(password):
    from options import options
    return options.password_hash == password_hash(password, options.password_salt)


def check_login(redirect=False):
    from options import options
    qdict = web.input()

    try:
        if options.no_password:
            return True

        if web.config._session.user == 'admin':
            return True
    except KeyError:
        pass

    if 'pw' in qdict:
        if test_password(qdict['pw']):
            return True
        if redirect:
            raise web.unauthorized()
        return False

    if redirect:
        raise web.seeother('/login')
    return False


signin_form = form.Form(
    form.Password('password', description='Password:'),
    validators=[
        form.Validator(
            "Incorrect password, please try again",
            lambda x: test_password(x["password"])
        )
    ]
)


def get_input(qdict, key, default=None, cast=None):
    result = default
    if key in qdict:
        result = qdict[key]
        if cast is not None:
            result = cast(result)
    return result
