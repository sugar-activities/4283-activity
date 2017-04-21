# Copyright (C), 2009 Aleksey Lim
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

import gtk
import wnck
import hippo
import gobject

from sugar import wm
from sugar.graphics import style

from zerosugar.util import www
from zerosugar.launcher.analysis import Probe


class Window(gtk.Window):

    __gsignals__ = {
        'stop': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
        }

    def __init__(self, flask, bundle_id, activity_id, verbose_messages):
        gtk.Window.__init__(self)

        self.props.type_hint = gtk.gdk.WINDOW_TYPE_HINT_NORMAL
        self.props.decorated = False

        canvas = hippo.Canvas()
        canvas.modify_bg(gtk.STATE_NORMAL, style.COLOR_WHITE.get_gdk_color())
        self.add(canvas)
        canvas.show()

        box = hippo.CanvasBox(
                padding=style.GRID_CELL_SIZE * 2,
                spacing=style.GRID_CELL_SIZE)
        canvas.set_root(box)

        header = hippo.CanvasBox()
        box.append(header, hippo.PACK_EXPAND)

        self._footer = Probe(flask, verbose_messages)
        self._footer.connect('stop',
                lambda sender: self.emit('stop'))
        box.append(self._footer, hippo.PACK_EXPAND)

        flask.connect('finished',
                lambda sender: self._footer.switch_to_complete())
        flask.connect('cancelled', self.__cancelled_cb)

        self.connect('realize', self.__realize_cb, bundle_id, activity_id)

    def switch_to_error(self):
        self._footer.switch_to_error()

    def __cancelled_cb(self, sender):
        self._footer.switch_to_error()

    def __realize_cb(self, window, bundle_id, activity_id):
        if bundle_id:
            wm.set_bundle_id(window.window, bundle_id)
        if activity_id:
            wm.set_activity_id(window.window, activity_id)
