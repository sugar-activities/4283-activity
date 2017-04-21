# Copyright (C) 2010, Aleksey Lim
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
from ConfigParser import ConfigParser

from zerosugar.util import www
from zerosugar.util.logger import logger

CACHE_DIR = '.0sugar'

def get_info():
    bundle_path = os.environ.get('SUGAR_BUNDLE_PATH')
    if not bundle_path:
        bundle_path = '.'

    info_file = os.path.join(bundle_path, 'activity', 'activity.info')
    if not os.path.exists(info_file):
        logger.error('Cannot find activity.info file in "%s" directory.',
                bundle_path)
        return None

    activity = ConfigParser()
    activity.read(info_file)

    if not activity.has_option('Activity', 'requires') and \
            not activity.has_option('Activity', 'suggests'):
        logger.error('Cannot find requires or suggests field in activity.info.')
        return None

    return activity

def bundle_path():
    if 'SUGAR_BUNDLE_PATH' in os.environ:
        return os.environ['SUGAR_BUNDLE_PATH']

    def find(path):
        if path == os.sep:
            return None
        elif os.path.exists(os.path.join(path, 'activity', 'activity.info')):
            return path
        else:
            return find(os.path.dirname(path))

    return find(os.path.abspath(os.curdir))
