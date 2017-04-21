# Copyright (C) 2009 Aleksey Lim
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

from gettext import gettext as _

import gtk
import hippo
import gobject

from sugar.graphics import style


class Probe(hippo.CanvasBox):

    __gsignals__ = {
        'stop': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
        }

    def __init__(self, flask, verbose_messages):
        hippo.CanvasBox.__init__(self)
        self.props.spacing = style.DEFAULT_SPACING

        flask.connect('verbose', self.__verbose_cb)
        flask.connect('progress', self.__progress_cb)
        flask.connect('key_confirm', self.__key_confirm_cb)

        self._page = None
        self._key = None

        # verbose

        self._verbose = gtk.TextView()
        self._verbose.props.wrap_mode = gtk.WRAP_WORD
        self._verbose.props.editable = False
        self._verbose.props.buffer.props.text = verbose_messages

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.add(self._verbose)
        scrolled.show_all()

        expander = gtk.Expander(_('Details'))
        expander.add(scrolled)
        self.append(hippo.CanvasWidget(widget=expander), hippo.PACK_EXPAND)

        # progress page

        self._progress_page = hippo.CanvasBox(
                spacing=style.DEFAULT_SPACING,
                orientation=hippo.ORIENTATION_VERTICAL)

        self._progress = gtk.ProgressBar()
        self._progress.set_size_request(-1, style.SMALL_ICON_SIZE)
        self._progress.modify_bg(gtk.STATE_INSENSITIVE,
                style.COLOR_WHITE.get_gdk_color())
        self._progress_page.append(hippo.CanvasWidget(widget=self._progress))

        cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)
        cancel_button.connect('clicked', self.__cancel_button_clicked_cb,
                flask)
        self._progress_page.append(hippo.CanvasWidget(
                widget=cancel_button,
                xalign=hippo.ALIGNMENT_CENTER))

        # confirm page

        self._confirm_page = hippo.CanvasBox(
                spacing=style.DEFAULT_SPACING,
                orientation=hippo.ORIENTATION_HORIZONTAL,
                xalign=hippo.ALIGNMENT_CENTER)

        self._confirm_caption = hippo.CanvasText()
        self._confirm_page.append(self._confirm_caption)

        self._accept_button = gtk.Button(stock=gtk.STOCK_YES)
        self._accept_button.connect('clicked',
                self.__accept_button_clicked_cb, flask)
        self._confirm_page.append(hippo.CanvasWidget(
                widget=self._accept_button))

        deny_button = gtk.Button(stock=gtk.STOCK_NO)
        deny_button.connect('clicked', self.__deny_button_clicked_cb, flask)
        self._confirm_page.append(hippo.CanvasWidget(widget=deny_button))

        # complete page

        self._complete_page = hippo.CanvasBox(
                spacing=style.DEFAULT_SPACING,
                orientation=hippo.ORIENTATION_VERTICAL)

        stop_button = gtk.Button(stock=gtk.STOCK_STOP)
        stop_button.connect('clicked', lambda button: self.emit('stop'))
        self._complete_page.append(hippo.CanvasWidget(
                widget=stop_button,
                xalign=hippo.ALIGNMENT_CENTER))

        # error page

        self._error_page = hippo.CanvasBox(
                spacing=style.DEFAULT_SPACING,
                orientation=hippo.ORIENTATION_VERTICAL)

        stop_button = gtk.Button(stock=gtk.STOCK_DIALOG_ERROR)
        stop_button.connect('clicked', lambda button: self.emit('stop'))
        self._error_page.append(hippo.CanvasWidget(
                widget=stop_button,
                xalign=hippo.ALIGNMENT_CENTER))

    def switch_to_complete(self):
        self._switch_view(self._complete_page)

    def switch_to_error(self):
        self._switch_view(self._error_page)

    def _switch_view(self, widget):
        if self._page == widget:
            return
        if self._page is not None:
            self.remove(self._page)
        self.prepend(widget)
        self._page = widget

    def __cancel_button_clicked_cb(self, button, flask):
        flask.cancel()

    def __verbose_cb(self, flask, message):
        buf = self._verbose.props.buffer
        if buf.props.text:
            buf.props.text += "\n"
        buf.props.text += message

    def __progress_cb(self, flask, fraction):
        if fraction < 0:
            self._progress.pulse()
        else:
            self._progress.props.fraction = fraction
        self._switch_view(self._progress_page)

    def __key_confirm_cb(self, flask, key):
        self._confirm_caption.props.text = \
                _('Do you trust to %s?') % key.user_id
        self._switch_view(self._confirm_page)
        self._key = key

    def __accept_button_clicked_cb(self, button, flask):
        assert(self._key)
        self._switch_view(self._progress_page)
        flask.accept(self._key)
        self._key = None

    def __deny_button_clicked_cb(self, button, flask):
        flask.deny()
