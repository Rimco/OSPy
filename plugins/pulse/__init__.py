#!/usr/bin/env python
# This plugin pulses a selected circuit with a 1 Hz signal with adjusted time. (For discover the location of a valve).

import json
import time
import web
import traceback

from threading import Thread, Event

from ospy import helpers
from ospy.stations import stations
from ospy.options import options
from ospy.webpages import ProtectedPage
from plugins import PluginOptions, plugin_url
from ospy.log import log

NAME = 'Pulse Output Test'
LINK = 'start_page'

pulse_options = PluginOptions(
    NAME,
    {
        'stations_count': stations.count(),
        'use_plugin': False,
        'time_test': 30,
        'select_output': '0' 
    }
)

class PulseSender(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self._stop = Event()

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

    def run(self):
        while not self._stop.is_set():
           try:
               if pulse_options['use_plugin']:
                   log.clear(NAME)
                   log.info(NAME, 'Test started for ' + str(pulse_options['time_test']) + ' sec.')
                   for x in range(0, int(pulse_options['time_test'])):                 
                      if pulse_options['use_plugin']:   
                         selected_stat = int(pulse_options['select_output'])                 
                         stations.activate(selected_stat)
                         self._sleep(1)
                         stations.deactivate(selected_stat)
                         self._sleep(1)

                   log.finish_run(None)                              
                   stations.clear() 
                   options.scheduler_enabled = True
                   self._sleep(1)
                   pulse_options['use_plugin'] = False  
                   log.clear(NAME)
                   log.info(NAME, 'Test was successfully completed.')
             
           except Exception:
               err_string = ''.join(traceback.format_exc())
               log.error(NAME, 'Pulse plug-in:\n' + err_string)
               self._sleep(60)


sender = None


################################################################################
# Helper functions:                                                            #
################################################################################
def start():
    global sender
    if sender is None:
        sender = PulseSender()


def stop():
    global sender
    if sender is not None:
        sender.stop()
        sender.join()
        sender = None


################################################################################
# Web pages:                                                                   #
################################################################################
class start_page(ProtectedPage):
    """Load an html start page"""

    def GET(self):
        if pulse_options['use_plugin']:          
            log.info(NAME, 'Test is enabled.')
           
        else:
            log.info(NAME, 'Test is disabled.')
                      
        return self.plugin_render.pulse(pulse_options, log.events(NAME))

    def POST(self):
        pulse_options.web_update(web.input())
        if sender is not None:
            if pulse_options['use_plugin']:  
               log.clear(NAME)
               log.info(NAME, 'Testing Output: ' + str(int(pulse_options['select_output'])+1) )
               options.scheduler_enabled = False
               log.info(NAME, 'Scheduler is disabled if test running...')
               log.finish_run(None)
               stations.clear()
               sender.update()
        raise web.seeother(plugin_url(start_page), True)


class stop_page(ProtectedPage):
    """Load an html stop page"""
    def POST(self):
        if sender is not None:
            if pulse_options['use_plugin']:  
               log.clear(NAME)
               log.info(NAME, 'Test is stoped.') 
               pulse_options['use_plugin'] = False
               options.scheduler_enabled = True
               log.info(NAME, 'Scheduler is now enabled...')
               log.finish_run(None)
               stations.clear()
               sender.update()
        raise web.seeother(plugin_url(start_page), True)
     

class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(pulse_options)


