# Copyright (C) 2009, Thomas Leonard
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
import re
import subprocess

from zerosugar.util.logger import logger


def system(cmd, **kwargs):
    while True:
        process = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE,
                stdout=subprocess.PIPE, **kwargs)
        stdout, stderr = process.communicate()
        if stdout is None:
            logger.warn('XXX first communicate() may returns None ' \
                        'for stdout on XO-1')
            continue
        if process.returncode:
            return None, stderr
        else:
            return stdout.strip(), None

def gnupg():
    global _gnupg

    if _gnupg is False:
        if system('which gpg')[1] is None:
            _gnupg = 'gpg'
        elif system('which gpg2')[1] is None:
            _gnupg = 'gpg2'
        else:
            _gnupg = None

    return _gnupg

def unescape(uri):
    uri = uri.replace('#', '/')
    if '%' not in uri:
        return uri
    return re.sub('%[0-9a-fA-F][0-9a-fA-F]', lambda match:
            chr(int(match.group(0)[1:], 16)), uri).decode('utf-8')

def escape(uri):
	return re.sub('[^-_.a-zA-Z0-9]', lambda match:
            '%%%02x' % ord(match.group(0)), uri.encode('utf-8'))

_gnupg = False
