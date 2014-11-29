#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Rimco'

# System imports
import datetime
import logging
import os
import random
import subprocess
import time
import errno
from threading import Thread
from collections import namedtuple

# Local imports
import web
from web import form
from web.session import sha1


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
        return "IP unavailable"


def get_mac():
    """Retrun MAC from file"""
    try:
        myMAC = open('/sys/class/net/eth0/address').read()
        return str(myMAC)
    except:
        return str('none')


def get_meminfo():
    """Return the information in /proc/meminfo as a dictionary"""
    try:
        meminfo = {}
        with open('/proc/meminfo') as f:
            for line in f:
                meminfo[line.split(':')[0]] = line.split(':')[1].strip()
        return meminfo
    except:
        return None


def get_netdevs():
    """RX and TX bytes for each of the network devices"""
    try:
        with open('/proc/net/dev') as f:
            net_dump = f.readlines()
        device_data = {}
        data = namedtuple('data', ['rx', 'tx'])
        for line in net_dump[2:]:
            line = line.split(':')
            if line[0].strip() != 'lo':
                device_data[line[0].strip()] = data(float(line[1].split()[0])/(1024.0*1024.0),
                                                    float(line[1].split()[8])/(1024.0*1024.0))
        return device_data
    except:
        return None


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


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def duration_str(total_seconds):
    minutes, seconds = divmod(total_seconds, 60)
    return '%02d:%02d' % (minutes, seconds)


def timedelta_duration_str(time_delta):
    return duration_str(time_delta.total_seconds())


def timedelta_time_str(time_delta, with_seconds=False):
    days, remainder = divmod(time_delta.total_seconds(), 24*3600)
    hours, remainder = divmod(remainder, 3600)
    if hours == 24:
        hours = 0
    minutes, seconds = divmod(remainder, 60)
    return '%02d:%02d' % (hours, minutes) + ((':%02d' % seconds) if with_seconds else '')


def minute_time_str(minute_time, with_seconds=False):
    return timedelta_time_str(datetime.timedelta(minutes=minute_time), with_seconds)


def short_day(index):
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][index]


def long_day(index):
    return ["Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday"][index]


def stop_onrain():
    """Stop stations that do not ignore rain."""
    from stations import stations
    for station in stations.get():
        if not station.ignore_rain:
            station.activated = False


def save_to_options(qdict):
    from options import options

    for option in options.OPTIONS:
        key = option['key']
        multi_enum = option.get('multi_options')
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
            elif multi_enum:
                if hasattr(multi_enum, '__call__'):
                    multi_enum = multi_enum()

                value = []
                for name in multi_enum:
                    v_name = key + '_' + name
                    if v_name in qdict and qdict[v_name] and qdict[v_name] != "off":
                        value.append(name)
                options[key] = value
            else:
                if isinstance(option['default'], bool):
                    options[key] = False


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
