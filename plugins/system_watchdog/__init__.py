# !/usr/bin/env python
# this plugins enable or disable watchdog 


from threading import Thread, Event
import time
import subprocess
import os
import re
import sys
import traceback

import web
from ospy import helpers
from ospy.options import options
from ospy.helpers import restart
from ospy.webpages import ProtectedPage
from ospy.log import log
from plugins import plugin_url


NAME = 'System Watchdog'
LINK = 'status_page'


class StatusChecker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.started = Event()
        
        self._stop = Event()

        self.status = {
            'service_install': False,
            'service_state': False}

        self._sleep_time = 0
        self.start()

    def stop(self):
        self._stop.set()

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0 and not self._stop.is_set():
            time.sleep(1)
            self._sleep_time -= 1

    def _is_installed(self):
        """Returns watchdog is instaled."""
        if not os.path.exists("/usr/sbin/watchdog"):       # if watchdog is not installed
           log.info(NAME, 'Watchdog is not installed. For continue press button install watchdog.')
        else:
           self.status['service_install'] = True

    def _is_started(self):
        """Returns true if watchdog is started."""
        cmd = "sudo service watchdog status"
        run_process(cmd) 
        try: 
           import commands
           output = commands.getoutput('ps -A')
           if 'watchdog' in output:
              self.status['service_state'] = True
           else:
              self.status['service_state'] = False       

        except Exception:
                self.started.set()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                log.error(NAME, 'System watchodg plug-in:\n' + err_string)
   
       
    def run(self):
        log.clear(NAME)
        self._is_installed()
        self._is_started()

        while not self._stop.is_set():
            try:
                self.started.set()
                self._sleep(3600)

            except Exception:
                self.started.set()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                log.error(NAME, 'System watchodg plug-in:\n' + err_string)
                self._sleep(60)


checker = None


################################################################################
# Helper functions:                                                            #
################################################################################
def start():
    global checker
    if checker is None:
        checker = StatusChecker()


def stop():
    global checker
    if checker is not None:
        checker.stop()
        checker.join()
        checker = None

def run_process(cmd):
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.STDOUT, # merge stdout and stderr
        stdout=subprocess.PIPE,
        shell=True)
    output = proc.communicate()[0]
    text = re.sub('\x1b[^m]*m', '', output) 
    log.info(NAME, text)


################################################################################
# Web pages:                                                                   #
################################################################################
class status_page(ProtectedPage):
    """Load an html page."""

    def GET(self):  
        log.clear(NAME)
        cmd = "sudo service watchdog status"
        run_process(cmd)
        return self.plugin_render.system_watchdog(checker.status, log.events(NAME))


class install_page(ProtectedPage):
    """Instalation watchdog page"""

    def GET(self):
        log.clear(NAME)
        cmd = "sudo echo 'bcm2708_wdog' >> /etc/modules"
        run_process(cmd)
        cmd = "sudo modprobe bcm2708_wdog"
        run_process(cmd)
        cmd = "sudo apt-get install -y watchdog chkconfig"
        run_process(cmd)
        cmd = "sudo chkconfig watchdog on"
        run_process(cmd)
        log.info(NAME, 'Saving config to /etc/watchdog.conf')

        # http://linux.die.net/man/5/watchdog.conf
        f = open("/etc/watchdog.conf","w")
        f.write("interval = 10\n")
        f.write("max-load-1 = 24\n")
        f.write("watchdog-device = /dev/watchdog\n")  
        f.write("realtime = yes\n")
        f.write("priority = 1\n")
        f.write("test-timeout = 0\n")  
        f.close()
        restart(3)
        return self.core_render.restarting(plugin_url(status_page))


class stop_page(ProtectedPage):
    """Stop watchdog service page"""

    def GET(self):
        log.clear(NAME)
        cmd = "sudo service watchdog stop"
        run_process(cmd)
        cmd = "sudo update-rc.d watchdog remove" 
        run_process(cmd)
        restart(3)
        return self.core_render.restarting(plugin_url(status_page))
      

class start_page(ProtectedPage):
    """Start watchdog service page"""

    def GET(self):
        log.clear(NAME)
        cmd = "sudo chkconfig watchdog on" 
        run_process(cmd)
        cmd = "sudo /etc/init.d/watchdog start"
        run_process(cmd)
        restart(3)
        return self.core_render.restarting(plugin_url(status_page))

