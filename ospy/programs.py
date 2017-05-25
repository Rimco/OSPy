#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

# System imports
import datetime
import logging
import traceback
import math

# Local imports
from ospy.helpers import minute_time_str, short_day
from ospy.options import options
from ospy.weather import weather
from ospy.stations import stations
from ospy.log import log


class ProgramType(object):
    DAYS_SIMPLE = 0
    DAYS_ADVANCED = 1
    REPEAT_SIMPLE = 2
    REPEAT_ADVANCED = 3
    WEEKLY_ADVANCED = 4
    CUSTOM = 5
    WEEKLY_WEATHER = 6

    FRIENDLY_NAMES = {
        DAYS_SIMPLE: 'Selected days (Simple)',
        DAYS_ADVANCED: 'Selected days (Advanced)',
        REPEAT_SIMPLE: 'Repeating (Simple)',
        REPEAT_ADVANCED: 'Repeating (Advanced)',
        WEEKLY_ADVANCED: 'Weekly (Advanced)',
        CUSTOM: 'Custom',
        WEEKLY_WEATHER: 'Weekly (Weather based)',
    }

ProgramType.NAMES = {getattr(ProgramType, x): x for x in dir(ProgramType) if not x.startswith('_') and
                                                                             isinstance(getattr(ProgramType, x), int)}

class _Program(object):
    SAVE_EXCLUDE = ['SAVE_EXCLUDE', 'index', '_programs', '_loading']

    def __init__(self, programs_instance, index):
        self._programs = programs_instance
        self._loading = True

        self.name = "Program %02d" % (index+1 if index >= 0 else abs(index))
        self._stations = []
        self.enabled = True

        self.fixed = 0
        self.cut_off = 0

        self._schedule = []
        self._station_schedule = {}
        self._modulo = 24*60
        self._manual = False  # Non-repetitive (run-once) if True
        self._start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)

        self.type = ProgramType.CUSTOM
        self.type_data = [[]]
        if index >= 0:
            options.load(self, index)
        self._loading = False

    @property
    def index(self):
        try:
            return self._programs.get().index(self)
        except ValueError:
            return -1

    @property
    def stations(self):
        return self._stations

    @stations.setter
    def stations(self, value):
        self._stations = value
        self.update_station_schedule()

    def update_station_schedule(self):
        self._station_schedule = {}

        if self.type != ProgramType.WEEKLY_WEATHER:
            for station in self.stations:
                self._station_schedule[station] = self._schedule
        else:
            now = datetime.datetime.now()
            week_start = datetime.datetime.combine(now.date() -
                                                   datetime.timedelta(days=now.weekday()),
                                                   datetime.time.min)
            self._start = week_start
            try:
                irrigation_min, irrigation_max, run_max, pause_ratio, pem_mins = self.type_data

                # Backup plan in case we don't get data:
                for station in self.stations:
                    self._station_schedule[station] = []
                    station_duration = min(60, int(run_max*60/stations.get(station).precipitation))
                    for pem_min, _ in pem_mins:
                        self._station_schedule[station] = self._update_schedule(self._station_schedule[station], self.modulo, pem_min, pem_min+station_duration)
                        self._station_schedule[station] = self._update_schedule(self._station_schedule[station], self.modulo, 7*1440 + pem_min, 7*1440 + pem_min+station_duration)
                        self._station_schedule[station] = self._update_schedule(self._station_schedule[station], self.modulo, 14*1440 + pem_min, 14*1440 + pem_min+station_duration)

                pems = [(week_start + datetime.timedelta(minutes=x), y) for x, y in pem_mins]
                pems += [(week_start + datetime.timedelta(days=7, minutes=x), y) for x, y in pem_mins]
                pems += [(week_start + datetime.timedelta(days=-7, minutes=x), y) for x, y in pem_mins]
                pems = sorted(pems)
                pems = [x for x in pems if x[0] >= now - datetime.timedelta(hours=12)]
                pems = [x for x in pems if (x[0].date() - now.date()).days < 10]

                min_eto_day = now.date()
                station_irrigation = {}
                station_balance = {}
                for station in self.stations:
                    if stations.get(station).last_balance_date < now.date() - datetime.timedelta(days=21):
                        stations.get(station).last_balance_date = now.date() - datetime.timedelta(days=21)
                        stations.get(station).last_balance = 0.0

                    min_eto_day = min(min_eto_day, stations.get(station).last_balance_date)
                    station_irrigation[station] = {}
                    station_balance[station] = {}

                for run in log.finished_runs():
                    if run['station'] in station_irrigation:
                        day_index = (run['start'].date() - now.date()).days
                        irrigation = (run['end'] - run['start']).total_seconds() / 3600 * stations.get(run['station']).precipitation
                        if day_index not in station_irrigation[run['station']]:
                            station_irrigation[run['station']][day_index] = 0.0
                        station_irrigation[run['station']][day_index] += irrigation

                day_eto = {}
                day_rain = {}
                for day_index in range((min_eto_day - now.date()).days, 10):
                    check_date = now.date() + datetime.timedelta(days=day_index)
                    day_eto[day_index] = weather.get_eto(check_date)
                    day_rain[day_index] = weather.get_rain(check_date)

                to_sprinkle = {}

                for station in self.stations:
                    to_sprinkle[station] = []
                    station_balance[station][(stations.get(station).last_balance_date - now.date()).days] = stations.get(station).last_balance
                    for day_index in range((stations.get(station).last_balance_date - now.date()).days + 1, 10):
                        if day_index not in station_irrigation[station]:
                            station_irrigation[station][day_index] = 0.0

                        station_balance[station][day_index] = station_balance[station][day_index-1] \
                                                            + station_irrigation[station][day_index] \
                                                            - day_eto[day_index] + day_rain[day_index]
                        station_balance[station][day_index] = min(station_balance[station][day_index],
                                                                  stations.get(station).capacity)

                        if day_index == -7:
                            stations.get(station).last_balance_date = now.date() + datetime.timedelta(days=day_index)
                            stations.get(station).last_balance = station_balance[station][day_index]

                    for index, (pem, prio) in enumerate(pems):
                        day_index = (pem.date() - now.date()).days

                        better_days = [x for x in pems[index+1:] if x[1] > prio]
                        amount = 0

                        # The best day:
                        if not better_days:
                            if -station_balance[station][day_index] >= irrigation_min:
                                amount = min(irrigation_max, -station_balance[station][day_index])
                        else:
                            target_index = (better_days[0][0].date() - now.date()).days

                            later_deficit_max = min(station_balance[station][later_day_index] for later_day_index in range(day_index, target_index + 1))
                            if -later_deficit_max > irrigation_max:
                                amount = min(max(irrigation_min, -later_deficit_max - irrigation_max), irrigation_max)

                        if amount > 0:
                            logging.debug('Weather based schedule for station: %d: PEM: %s, priority: %s, amount: %f.', station, str(pem), prio, amount)
                            for later_day_index in range(day_index, 10):
                                station_balance[station][later_day_index] += amount
                            week_min = (pem - week_start).total_seconds() / 60

                            intervals = [amount]
                            while any(x > run_max for x in intervals):
                                new_len = len(intervals) + 1
                                intervals = [amount / new_len] * new_len

                            for interval in intervals:
                                station_duration = int(interval*60/stations.get(station).precipitation)
                                to_sprinkle[station] = self._update_schedule(to_sprinkle[station], self.modulo, week_min, week_min+station_duration)
                                week_min += station_duration + int(station_duration*pause_ratio)

                    logging.debug('Weather based deficit for station: %d: %s', station, str(sorted([((now.date() + datetime.timedelta(days=x)).isoformat(), y) for x, y in station_balance[station].iteritems()])))

                self._station_schedule = to_sprinkle
            except Exception:
                logging.warning('Could create weather based schedule:\n' + traceback.format_exc())

    @property
    def schedule(self):
        return [interval[:] for interval in self._schedule]

    @schedule.setter
    def schedule(self, value):
        new_schedule = []
        for interval in value:
            new_schedule = self._update_schedule(new_schedule, self.modulo, interval[0], interval[1])

        self._schedule = new_schedule
        self.update_station_schedule()
        self.type = ProgramType.CUSTOM
        self.type_data = [value]

    @property
    def modulo(self):
        return self._modulo

    @property
    def manual(self):
        return self._manual

    @property
    def start(self):
        return self._start

    def start_now(self):
        first_offset = datetime.timedelta(minutes=self._schedule[0][0])
        self._manual = True
        self._schedule = [interval for interval in self.typed_schedule() if interval[1] <= 1440]
        self.update_station_schedule()
        self._start = datetime.datetime.now() - first_offset  # Make sure the first interval starts now

    def _day_str(self, index):
        if self.type != ProgramType.CUSTOM and self.type != ProgramType.REPEAT_ADVANCED:
            return short_day(index)
        else:
            return "Day %d" % (index + 1)

    def summary(self):
        result = "Unknown schedule"
        if self.type == ProgramType.CUSTOM:
            if self.manual:
                result = "Custom schedule running once on %s" % self.start.strftime("%Y-%m-%d")
            else:
                if self._modulo % 1440 == 0 and self._modulo > 0:
                    days = (self._modulo / 1440)
                    if days == 1:
                        result = "Custom schedule repeating daily"
                    else:
                        result = "Custom schedule repeating every %d days" % (self._modulo / 1440)
                else:
                    result = "Custom schedule repeating every %d minutes" % self._modulo
        elif self.type == ProgramType.REPEAT_SIMPLE:
            if self.type_data[4] == 1:
                result = "Simple daily schedule"
            else:
                result = "Simple schedule repeating every %d days" % self.type_data[4]
        elif self.type == ProgramType.REPEAT_ADVANCED:
            if self.type_data[1] == 1:
                result = "Advanced daily schedule"
            else:
                result = "Advanced schedule repeating every %d days" % self.type_data[1]
        elif self.type == ProgramType.DAYS_SIMPLE:
            result = "Simple schedule on " + ' '.join([self._day_str(x) for x in self.type_data[4]])
        elif self.type == ProgramType.DAYS_ADVANCED:
            result = "Advanced schedule on " + ' '.join([self._day_str(x) for x in self.type_data[1]])
        elif self.type == ProgramType.WEEKLY_ADVANCED:
            result = "Advanced weekly schedule"
        elif self.type == ProgramType.WEEKLY_WEATHER:
            result = "Weather based schedule on " + ' '.join([self._day_str(x) for x in set([int(y/1440) for y, z in self.type_data[-1]])])
        return result

    def details(self):
        result = "Unknown schedule"

        if len(self._schedule) == 0:
            result = "Empty schedule"
        elif self.type == ProgramType.REPEAT_SIMPLE or self.type == ProgramType.DAYS_SIMPLE:
            start_time = minute_time_str(self.type_data[0])
            duration = self.type_data[1]
            pause = self.type_data[2]
            repeat = self.type_data[3]
            result = "Starting: <span class='val'>%s</span> for <span class='val'>%d</span> minutes<br>" % (start_time, duration)
            if repeat:
                result += ("Repeat: <span class='val'>%s</span> " + ("times" if repeat > 1 else "time") +
                           " with a <span class='val'>%d</span> minute delay<br>") % (repeat, pause)

        elif self.type == ProgramType.CUSTOM or \
                self.type == ProgramType.REPEAT_ADVANCED or \
                self.type == ProgramType.WEEKLY_ADVANCED:
            if self.type == ProgramType.CUSTOM:
                days = self._modulo / 1440
                intervals = self.schedule
            elif self.type == ProgramType.WEEKLY_ADVANCED:
                days = self._modulo / 1440
                intervals = self.type_data[0]
            else:
                days = self.type_data[1]
                intervals = self.type_data[0]

            if days == 1:
                result = "Intervals: "
                for interval in intervals:
                    result += "<span class='val'>%s-%s</span> " % (minute_time_str(interval[0]),
                                                                   minute_time_str(interval[1]))
            else:
                day_strs = {}
                for interval in intervals:
                    day_start = int(interval[0] / 1440)
                    day_end = int(interval[1] / 1440)
                    if day_start == day_end:
                        if day_start not in day_strs:
                            day_strs[day_start] = "%s: " % self._day_str(day_start)
                        day_strs[day_start] += "<span class='val'>%s-%s</span> " % (minute_time_str(interval[0]),
                                                                                    minute_time_str(interval[1]))
                    else:
                        if day_start not in day_strs:
                            day_strs[day_start] = "%s: " % self._day_str(day_start)
                        if day_end not in day_strs:
                            day_strs[day_end] = "%s: " % self._day_str(day_end)
                        day_strs[day_start] += "<span class='val'>%s-%s</span> " % (minute_time_str(interval[0]),
                                                                                    minute_time_str(1440))
                        day_strs[day_end] += "<span class='val'>%s-%s</span> " % (minute_time_str(1440),
                                                                                  minute_time_str(interval[1]))
                result = '<br>'.join(day_strs.values())

        elif self.type == ProgramType.DAYS_ADVANCED:
            result = 'Intervals: '
            for interval in self.type_data[0]:
                result += "<span class='val'>%s-%s</span> " % (minute_time_str(interval[0]),
                                                               minute_time_str(interval[1]))
        elif self.type == ProgramType.WEEKLY_WEATHER:
            irrigation_min = self.type_data[0]
            irrigation_max = self.type_data[1]
            result = "For <span class='val'>%d</span> to <span class='val'>%d</span> mm<br>" % (irrigation_min, irrigation_max)
        return result

    def clear(self):
        self._schedule = []
        self.update_station_schedule()

    def set_days_simple(self, start_min, duration_min, pause_min, repeat_times, days):
        new_schedule = []
        for day in days:
            day_start_min = start_min + 1440 * day
            for i in range(repeat_times+1):
                new_schedule = self._update_schedule(new_schedule, 7*1440, day_start_min, day_start_min + duration_min)
                day_start_min += pause_min + duration_min

        self._modulo = 7*1440
        self._manual = False
        self._start = datetime.datetime.combine(datetime.date.today() -
                                                datetime.timedelta(days=datetime.date.today().weekday()),
                                                datetime.time.min)  # First day of current week
        self._schedule = new_schedule
        self.update_station_schedule()

        self.type = ProgramType.DAYS_SIMPLE
        self.type_data = [start_min, duration_min, pause_min, repeat_times, days[:]]

    def set_days_advanced(self, schedule, days):
        new_schedule = []
        for day in days:
            offset = 1440 * day
            for interval in schedule:
                new_schedule = self._update_schedule(new_schedule, 7*1440, interval[0] + offset, interval[1] + offset)

        self._modulo = 7*1440
        self._manual = False
        self._start = datetime.datetime.combine(datetime.date.today() -
                                                datetime.timedelta(days=datetime.date.today().weekday()),
                                                datetime.time.min)  # First day of current week
        self._schedule = new_schedule
        self.update_station_schedule()

        self.type = ProgramType.DAYS_ADVANCED
        self.type_data = [schedule, days[:]]

    def set_repeat_simple(self, start_min, duration_min, pause_min, repeat_times, repeat_days, start_date):
        new_schedule = []
        day_start_min = start_min
        for i in range(repeat_times+1):
            new_schedule = self._update_schedule(new_schedule, repeat_days*1440, day_start_min, day_start_min + duration_min)
            day_start_min += pause_min + duration_min

        self._modulo = repeat_days*1440
        self._manual = False
        self._start = datetime.datetime.combine(start_date, datetime.time.min)
        self._schedule = new_schedule
        self.update_station_schedule()

        self.type = ProgramType.REPEAT_SIMPLE
        self.type_data = [start_min, duration_min, pause_min, repeat_times, repeat_days, start_date]

    def set_repeat_advanced(self, schedule, repeat_days, start_date):
        new_schedule = []
        for interval in schedule:
            new_schedule = self._update_schedule(new_schedule, repeat_days*1440, interval[0], interval[1])

        self._schedule = new_schedule
        for station in self.stations:
            self._station_schedule[station] = new_schedule
        self._modulo = repeat_days*1440
        self._manual = False
        self._start = datetime.datetime.combine(start_date, datetime.time.min)

        self.type = ProgramType.REPEAT_ADVANCED
        self.type_data = [schedule, repeat_days, start_date]

    def set_weekly_advanced(self, schedule):
        new_schedule = []
        for interval in schedule:
            new_schedule = self._update_schedule(new_schedule, 7*1440, interval[0], interval[1])

        self._modulo = 7*1440
        self._manual = False
        self._start = datetime.datetime.combine(datetime.date.today() -
                                                datetime.timedelta(days=datetime.date.today().weekday()),
                                                datetime.time.min)  # First day of current week
        self._schedule = new_schedule
        self.update_station_schedule()

        self.type = ProgramType.WEEKLY_ADVANCED
        self.type_data = [schedule]

    def set_weekly_weather(self, irrigation_min, irrigation_max, run_max, pause_min, pems):
        new_schedule = []

        # Just fill in something, will be updated per station anyways:
        for pem, prio in pems:
            new_schedule = self._update_schedule(new_schedule, 21*1440, pem, pem + 1)
            new_schedule = self._update_schedule(new_schedule, 21*1440, 7*1440 + pem, 7*1440 + pem + 1)
            new_schedule = self._update_schedule(new_schedule, 21*1440, 14*1440 + pem, 14*1440 + pem + 1)

        self._modulo = 21*1440
        self._manual = False
        self._start = datetime.datetime.combine(datetime.date.today() -
                                                datetime.timedelta(days=datetime.date.today().weekday()),
                                                datetime.time.min)  # First day of current week
        self._schedule = new_schedule

        self.fixed = 1
        self.cut_off = 0
        self.type = ProgramType.WEEKLY_WEATHER
        self.type_data = [irrigation_min, irrigation_max, run_max, pause_min, pems[:]]
        self.update_station_schedule()

    # The following functions provide easy access to data of different types, returns default if not available

    def start_min(self):
        if self.type == ProgramType.DAYS_SIMPLE or self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[0]
        else:
            return 6*60

    def duration_min(self):
        if self.type == ProgramType.DAYS_SIMPLE or self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[1]
        else:
            return 30

    def pause_min(self):
        if self.type == ProgramType.DAYS_SIMPLE or self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[2]
        else:
            return 30

    def repeat_times(self):
        if self.type == ProgramType.DAYS_SIMPLE or self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[3]
        else:
            return 0

    def days(self):
        if self.type == ProgramType.DAYS_SIMPLE:
            return self.type_data[4]
        elif self.type == ProgramType.DAYS_ADVANCED:
            return self.type_data[1]
        elif self.type == ProgramType.WEEKLY_WEATHER:
            return list(set([int(y/1440) for y, z in self.type_data[-1]]))
        else:
            return []

    def repeat_days(self):
        if self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[4]
        elif self.type == ProgramType.REPEAT_ADVANCED:
            return self.type_data[1]
        elif self.type == ProgramType.WEEKLY_ADVANCED:
            return 7
        else:
            return max(1, int(self._modulo / 1440))

    def start_date(self):
        if self.type == ProgramType.REPEAT_SIMPLE:
            return self.type_data[5]
        elif self.type == ProgramType.REPEAT_ADVANCED:
            return self.type_data[2]
        else:
            return self._start

    def irrigation_min(self):
        if self.type == ProgramType.WEEKLY_WEATHER:
            return self.type_data[0]
        else:
            return 15

    def irrigation_max(self):
        if self.type == ProgramType.WEEKLY_WEATHER:
            return self.type_data[1]
        else:
            return 25

    def run_max(self):
        if self.type == ProgramType.WEEKLY_WEATHER:
            return self.type_data[2]
        else:
            return 10

    def pause_ratio(self):
        if self.type == ProgramType.WEEKLY_WEATHER:
            return self.type_data[3]
        else:
            return 0.25

    def pems(self):
        if self.type == ProgramType.WEEKLY_WEATHER:
            return self.type_data[4]
        else:
            return []

    def typed_schedule(self):
        if self.type == ProgramType.DAYS_ADVANCED:
            return self.type_data[0]
        elif self.type == ProgramType.REPEAT_ADVANCED:
            return self.type_data[0]
        elif self.type == ProgramType.WEEKLY_ADVANCED:
            return self.type_data[0]
        else:
            return self.schedule

    @staticmethod
    def _update_schedule(schedule, modulo, start_minute, end_minute):
        start_minute %= modulo
        end_minute %= modulo

        if end_minute < start_minute:
            end_minute += modulo

        if end_minute > modulo:
            new_entries = [
                [0, end_minute % modulo],
                [start_minute, modulo]
            ]
        else:
            new_entries = [[start_minute, end_minute]]

        new_schedule = schedule[:]

        while new_entries:
            entry = new_entries.pop(0)
            for existing in new_schedule:
                if existing[0] <= entry[0] < existing[1]:
                    entry[0] = existing[1]
                if existing[0] < entry[1] <= existing[1]:
                    entry[1] = existing[0]
                if entry[0] < existing[0] <= existing[1] < entry[1]:
                    new_entries.append([existing[1], entry[1]])
                    entry[1] = existing[0]

                if entry[1] - entry[0] <= 0:
                    break

            if entry[1] - entry[0] > 0:
                new_schedule.append(entry)
                new_schedule.sort(key=lambda ent: ent[0])

        return new_schedule

    def is_active(self, date_time, station):
        if station in self._station_schedule:
            schedule = self._station_schedule[station]
        else:
            schedule = []

        time_delta = date_time - self.start
        minute_delta = time_delta.days*24*60 + int(time_delta.seconds/60)

        if self.manual and minute_delta >= self.modulo:
            return False

        current_minute = minute_delta % self.modulo

        result = False
        for entry in schedule:
            if entry[0] <= current_minute < entry[1]:
                result = True
                break
            elif entry[0] <= current_minute+self.modulo < entry[1]:
                result = True
                break
            elif entry[0] > current_minute:
                break

        return result

    def active_intervals(self, date_time_start, date_time_end, station):
        if station in self._station_schedule:
            schedule = self._station_schedule[station]
        else:
            schedule = []

        result = []
        if self.manual:
            current_date_time = self.start
        else:
            start_delta = date_time_start - self.start
            start_minutes = (start_delta.days*24*60 + int(start_delta.seconds/60)) % self.modulo
            current_date_time = date_time_start - datetime.timedelta(minutes=start_minutes,
                                                                     seconds=date_time_start.second,
                                                                     microseconds=date_time_start.microsecond)

        while current_date_time < date_time_end:
            for entry in schedule:
                start = current_date_time + datetime.timedelta(minutes=entry[0])
                end = current_date_time + datetime.timedelta(minutes=entry[1])

                if end <= date_time_start:
                    continue

                if start >= date_time_end:
                    break

                result.append({
                    'start': start,
                    'end': end
                })

            if self.manual:
                break

            current_date_time += datetime.timedelta(minutes=self.modulo)

        return result

    def __setattr__(self, key, value):
        if key == 'modulo':
            self._modulo = value
            if not self._loading:
                self.schedule = self._schedule  # Convert to custom sequence
        elif key == 'manual':
            self._manual = value
            if not self._loading and value:
                self.schedule = self._schedule  # Convert to custom sequence
        elif key == 'start':
            if self._loading:  # Update start date to most recent possible
                while value <= datetime.datetime.today():
                    value += datetime.timedelta(minutes=self._modulo)
                self._start = value
            else:
                self._start = value
                self.schedule = self._schedule  # Convert to custom sequence
        else:
            super(_Program, self).__setattr__(key, value)
            if key not in self.SAVE_EXCLUDE:
                if not self._loading and self.index >= 0:
                    options.save(self, self.index)


class _Programs(object):
    def __init__(self):
        self._programs = []
        self.run_now_program = None

        i = 0
        while options.available(_Program, i):
            self._programs.append(_Program(self, i))
            i += 1

        options.add_callback('output_count', self._option_cb)
        weather.add_callback(self._weather_cb)

    def _option_cb(self, key, old, new):
        # Remove all stations that do not exist anymore
        for program in self._programs:
            program.stations = [station for station in program.stations if 0 <= station < new]

    def _weather_cb(self):
        # Remove all stations that do not exist anymore
        for program in self._programs:
            if program.type == ProgramType.WEEKLY_WEATHER:
                program.update_station_schedule()

    def add_program(self, program=None):
        if program is None:
            program = _Program(self, len(self._programs))
        self._programs.append(program)
        options.save(program, program.index)

    def create_program(self):
        """Returns a new program, but doesn't add it to the list."""
        return _Program(self, -1-len(self._programs))

    def remove_program(self, index):
        if 0 <= index < len(self._programs):
            del self._programs[index]

        for i in range(index, len(self._programs)):
            options.save(self._programs[i], i)  # Save programs using new indices

        options.erase(_Program, len(self._programs))  # Remove info in last index

    def run_now(self, index):
        if 0 <= index < len(self._programs):
            program = self._programs[index]
            if program.type != ProgramType.WEEKLY_ADVANCED and program.type != ProgramType.CUSTOM and program.type != ProgramType.WEEKLY_WEATHER:
                if len(program.schedule) > 0:
                    run_now_p = _Program(self, index)  # Create a copy using the information saved in options
                    run_now_p.start_now()
                    self.run_now_program = run_now_p

    def count(self):
        return len(self._programs)

    def get(self, index=None):
        if index is None:
            result = self._programs[:]
        else:
            result = self._programs[index]
        return result

    __getitem__ = get

programs = _Programs()