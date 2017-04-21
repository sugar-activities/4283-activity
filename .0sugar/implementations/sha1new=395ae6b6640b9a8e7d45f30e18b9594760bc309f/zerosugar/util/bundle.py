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

import tarfile
import zipfile

class Bundle(object):

    def __init__(self, bundle):
        if tarfile.is_tarfile(bundle):
            self._bundle = tarfile.open(bundle)
            self._do_get_names = self._bundle.getnames
            self._do_extractfile = self._bundle.extractfile

        elif zipfile.is_zipfile(bundle):
            self._bundle = zipfile.ZipFile(bundle)
            self._do_get_names = self._bundle.namelist
            self._do_extractfile = self._bundle.open

        else:
            raise Exception('Unsupported bundle type for %s file, it could ' \
                            'be either tar or zip.' % bundle)

    def get_names(self):
        return self._do_get_names()

    def extractfile(self, name):
        return self._do_extractfile(name)

    def extractall(self, path, members=None):
        self._bundle.extractall(path=path, members=members)
