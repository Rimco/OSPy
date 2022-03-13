#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

# System imports
import subprocess
import logging

##############################
#### Revision information ####
##############################

major_ver = 3
minor_ver = 0

try:
    revision = int(subprocess.check_output(['git', 'rev-list', '--count', '--first-parent', 'HEAD']))
except Exception:
    logging.warning("Could not use git to determine revision!")
    revision = 999
ver_str = '%d.%d.%d' % (major_ver, minor_ver, revision)

try:
    ver_date = subprocess.check_output(['git', 'log', '-1', '--format=%cd', '--date=short']).strip().decode('ascii')
except Exception:
    logging.warning("Could not use git to determine date of last commit!")
    ver_date = '2022'