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

import os
import subprocess
import tempfile
from gettext import gettext as _

import gobject

from zeroinstall.injector import model
from zeroinstall.injector import download
from zeroinstall.injector.iface_cache import iface_cache
from zeroinstall.injector.iface_cache import PendingFeed
from zeroinstall.injector.policy import Policy
from zeroinstall.injector.handler import Handler
from zeroinstall.support import tasks
from zeroinstall import version

from zerosugar.util import www
from zerosugar.util import injector
from zerosugar.util.logger import logger


_SYNC_DELAY = 200

_STATE_ACTIVE = 1
_STATE_PROGRESSED = 2


class Flask(gobject.GObject):

    __gsignals__ = {
        'progress': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                     [gobject.TYPE_FLOAT]),
        'finished': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
        'cancelled': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
        'key_confirm': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                        [gobject.TYPE_PYOBJECT]),
        'verbose': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                    [gobject.TYPE_STRING]),
    }

    def __init__(self):
        gobject.GObject.__init__(self)

        self._stopped = None
        self._cancelled = None
        self._root_link = None
        self._queue = []
        self._state = 0
        self._handler = _Handler(self.__key_confirm_cb, self.__report_error_cb)
        self._stat_all = 0
        self._stat_processed = 0
        self._cancelled_by_intention = False

    def get_cancelled_by_intention(self):
        return self._cancelled_by_intention

    cancelled_by_intention = property(get_cancelled_by_intention)

    def get_processed(self):
        return self._stat_processed

    processed = property(get_processed)

    def get_skipped(self):
        return self._stat_all - self._stat_processed

    skipped = property(get_skipped)

    def pull(self, feeds, network_use=None, force=False):

        def link_new(feed):
            root = _SolveLink(feed)
            if network_use is not None:
                root.policy.network_use = network_use
            root.policy.handler = self._handler
            root.force = force

            links = []
            if root.policy.need_download():
                links.append(root)

            return (root, links)

        self._pull(feeds, link_new)

    def refresh(self, feeds, freshness=None):

        def link_new(feed):
            root = _RefreshLink(feed)
            root.policy.handler = self._handler
            if freshness:
                root.policy.freshness = freshness
            return (root, [root])

        self._pull(feeds, link_new)

    def is_stale(self):
        if self.policy is None:
            return False

        if self.policy.solver.feeds_used is None:
            # solve it at forst
            self.policy.need_download()

        for url in self.policy.solver.feeds_used:
            feed = iface_cache.get_feed(url)
            if self.policy.is_stale(feed):
                return True

        return False

    def get_active(self):
        return bool(self._state & _STATE_ACTIVE)

    active = property(get_active)

    def get_policy(self):
        return self._link is not None and self._link.policy or None

    policy = property(get_policy)

    def cancel(self):
        if self._cancelled is not None:
            self._cancelled.trigger()
        self._cancelled_by_intention = True

    def accept(self, key):
        """ Accept keys that were requested by key_confirm event """
        msg = _('* trusting %s for %s;') % (key.fingerprint, key.domain)
        self.emit('verbose', msg)
        self._handler.accept(key)

    def deny(self):
        """ Deny keys that were requested by key_confirm event """
        msg = _('* key confirm was denied;')
        self.emit('verbose', msg)
        self._handler.deny()
        self.cancel()

    def get_environ(self):
        return injector.get_environ(self.policy)

    def get_main(self):
        return injector.get_main(self.policy)

    def _get_link(self):
        return self._queue and self._queue[-1] or self._root_link

    _link = property(_get_link)

    def _pull(self, feeds, link_new):
        if not self.active:
            self._root_link = None

        msg = _('Pull %s.') % ', '.join([_name(i) for i in feeds])
        self.emit('verbose', msg)

        self._stat_all = len(feeds)
        self._stat_processed = 0

        for uri in feeds:
            try:
                uri = model.canonical_iface_uri(uri)
                root, links = link_new(uri)
            except Exception, e:
                logger.exception('Fail to pull %s into queue.', uri)
                self.emit('verbose', str(e))
                self._cancel()
                return

            if self._root_link is None:
                self._root_link = root

            if links:
                self._queue.extend(links)
                self._stat_processed += 1

        if not self.active:
            if self._queue:
                self._start()
            else:
                self._finish()

    def _start(self):
        self._state = _STATE_ACTIVE

        if self._iterate(initial_start=True):
            gobject.timeout_add(_SYNC_DELAY, self._sync)
            self._cancelled = tasks.Blocker('cancel %s' % \
                    self._link.get_feed())
            self._wait()
        else:
            msg = _('Ready to use.')
            self.emit('verbose', msg)

    def _cancel(self):
        if self.policy is not None:
            for i in self._handler.monitored_downloads.values():
                i.abort()
        self._on_exit()
        self.emit('verbose', _('Cancelled.'))
        self.emit('cancelled')

    def _finish(self):
        self._on_exit()
        self.emit('verbose', _('Finished.'))
        self.emit('finished')

    def _on_exit(self):
        if self._state & _STATE_PROGRESSED:
            self.emit('progress', 1.0)

        msg = _('Processed: %s; skipped: %s.') % (self.processed, self.skipped)
        self.emit('verbose', msg)

        self._state = 0

    @tasks.async
    def _wait(self):
        blockers = [self._stopped, self._cancelled]
        yield blockers
        tasks.check(blockers)

    def _sync(self):
        if self._cancelled.happened:
            self._cancel()
            return False
        elif self._stopped.happened:
            return self._iterate()
        else:
            if not self._handler.is_confirming():
                fraction = self._link.get_fraction()
                self.emit('progress', fraction)
                self._state |= _STATE_PROGRESSED
            return True

    def _iterate(self, initial_start=False):
        if not initial_start:
            next_links = self._link.detach(self._stopped)

            if next_links is None:
                self._cancel()
                return False

            if next_links:
                next_names = [i.get_name() for i in next_links]
                next_names.reverse()
                logger.debug('Additional %s links were attached.', next_names)

            self._queue.pop()
            self._queue.extend(next_links)

            if not self._queue:
                self._finish()
                return False

        if self._link.policy is not None and \
                self._link.policy.root == self._root_link.policy.root:
            # in case if we restarted root link
            self._root_link = self._link

        logger.debug('Switch to %r.', self._link)

        self._link.connect('verbose',
                lambda sender, message: self.emit('verbose', message))

        try:
            self._stopped = self._link.attach()
        except Exception:
            import traceback
            logger.error(traceback.format_exc())
            self._cancel()
            return False

        if self._stopped is None:
            if self.policy is not None and self.policy.solver.ready:
                msg = _('* ready to use;')
                self.emit('verbose', msg)
                return self._iterate()
            else:
                msg = _('* failed;')
                self.emit('verbose', msg)
                self._cancel()
                return False

        return True

    def __key_confirm_cb(self, key):
        msg = _('* key %s confirm requested for %s;') % \
                (key.user_id, key.domain)
        self.emit('verbose', msg)
        self.emit('key_confirm', key)

    def __report_error_cb(self, e, traceback):
        logger.error(e)


class _Link(gobject.GObject):

    __gsignals__ = {
        'verbose': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                    [gobject.TYPE_STRING]),
    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.policy = None

    def get_fraction(self):
        return -1.

    def get_feed(self):
        if self.policy is None:
            return None
        else:
            return self.policy.root

    def get_name(self):
        return _name(self.get_feed())

    def attach(self):
        return None

    def detach(self, blocker):
        return []


class _SolveLink(_Link):
    name = 'Solve'

    def __init__(self, feed, seed=None):
        _Link.__init__(self)

        self.force = False

        iface_uri = model.canonical_iface_uri(feed)
        self.policy = Policy(iface_uri)
        self.policy.solver.record_details = True

        if seed is not None:
            self.policy.network_use = seed.policy.network_use
            self.policy.handler = seed.policy.handler
            self.force = seed.force

    def attach(self):
        if self.force or not self.policy.ready:
            msg = _('Download feed for service %s:') % \
                    self.get_name()
            self.emit('verbose', msg)
        else:
            msg = _('Download requirements for service %s:') % \
                    self.get_name()
            self.emit('verbose', msg)

        return self.policy.solve_with_downloads(force=self.force)

    def detach(self, blocker):
        if self.policy.solver.ready:
            for iface, __ in self.policy.implementation.items():
                msg = _('* %s done;') % _name(iface.uri)
                self.emit('verbose', msg)
            if self.policy.need_download():
                return [_DownloadLink(self)]
            else:
                return []

        zcompile = _SolveLink(www.IFACE_COMPILE, self)

        # at the end, we should restart current link
        next_links = [_SolveLink(self.policy.root, self)]
        failed = False
        need_build = False

        for iface, impl in self.policy.implementation.items():
            if impl is not None:
                msg = _('* %s done;') % _name(iface.uri)
                self.emit('verbose', msg)
                continue

            if self._has_source(iface):
                msg = _('* %s needs to be built from sources;') % \
                        _name(iface.uri)
                self.emit('verbose', msg)
                next_links.append(_BuildLink(iface.uri, zcompile))
                next_links.append(_SolveSourceLink(iface.uri, self))
                need_build = True
            else:
                reason = self.policy.solver.details.get(iface) or _('Unknown')
                msg = _('* %s failed to resolve due to "%s";') % \
                        (_name(iface.uri), reason)
                self.emit('verbose', msg)
                failed = True

        if failed and not need_build:
            return None

        # check for 0compile at first
        next_links.append(zcompile)
        msg = _('* add %s;') % zcompile.get_name()
        self.emit('verbose', msg)

        return next_links

    def _has_source(self, iface):
        for feed in iface.feeds:
            if feed.machine == 'src':
                return True

        for impl in iface.implementations.values():
            if impl.machine == 'src':
                return True

        return False


class _RefreshLink(_SolveLink):
    name = 'Refresh'

    def __init__(self, feed):
        _SolveLink.__init__(self, feed)

        self.policy.network_use = model.network_full

    def attach(self):
        msg = _('Refresh feed for service %s:') % self.get_name()
        self.emit('verbose', msg)
        return self.policy.solve_with_downloads(force=True)

    def detach(self, blocker):
        return []


class _DownloadLink(_Link):
    name = 'Download'
    PENDING = 0
    FAILED = 1
    FALLBACK = 2

    def __init__(self, seed):
        _Link.__init__(self)

        self.policy = seed.policy
        self._seed = seed
        self._requires = {}

    def attach(self):
        msg = _('Download files for service %s:') % self.get_name()
        self.emit('verbose', msg)

        for iface, __ in self.policy.get_uncached_implementations():
            self._requires[iface.uri] = self.PENDING

        return self.policy.download_uncached_implementations()

    def detach(self, blocker):
        to_refresh = []

        if self.policy.need_download():
            for iface, impl in self.policy.get_uncached_implementations():
                if isinstance(impl, model.DistributionImplementation):
                    impl.upstream_stability = model.insecure
                    self._requires[iface.uri] = self.FALLBACK
                else:
                    self._requires[iface.uri] = self.FAILED

        for uri, state in self._requires.items():
            if state == self.FAILED:
                msg = _('* %s failed;')
            elif state == self.FALLBACK:
                msg = _('* %s failed from native packaging system, ' \
                        'will try pure zero ones;')
            else:
                msg = _('* %s done;')
            self.emit('verbose', msg % _name(uri))

        if self.FAILED in self._requires.values():
            return None
        elif set([self.PENDING]) == set(self._requires.values()):
            return []
        else:
            root_link = self._seed.__class__(self.policy.root, self._seed)
            return [root_link] + to_refresh

    def get_fraction(self):
        total = self.policy.handler.total_bytes_downloaded
        done = total

        for i in self.policy.handler.monitored_downloads.values():
            if i.status != download.download_fetching:
                continue
            so_far = i.get_bytes_downloaded_so_far()
            # Guess about 4K for feeds/icons
            total += i.expected_size or max(4096, so_far)
            done += so_far

        if not total:
            return 0.
        else:
            return float(done) / total


class _SolveSourceLink(_SolveLink):
    name = 'SolveSource'

    def __init__(self, feed, seed):
        _SolveLink.__init__(self, feed, seed)

        self.policy.src = True

    def detach(self, blocker):
        if self.policy.solver.ready:
            msg = _('* sources found;')
            self.emit('verbose', msg)
        else:
            msg = _('* failed to find sources;')
            self.emit('verbose', msg)
            return None

        return [_DownloadLink(self)]


class _BuildLink(_Link):
    name = 'Build'

    def __init__(self, src_uri, seed):
        _Link.__init__(self)

        self.policy = seed.policy
        self._src_uri = src_uri
        self._child = None
        self._blocker = None

    def attach(self):
        msg = _('Build service %s from sources:') % self.get_name()
        self.emit('verbose', msg)

        self._blocker = tasks.Blocker('build %s' % self._src_uri)

        command = (injector.get_main(self.policy), 'autocompile', self._src_uri)
        self._child = subprocess.Popen(command,
                env=injector.get_environ(self.policy),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        gobject.io_add_watch(self._child.stdout,
                gobject.IO_IN | gobject.IO_HUP | gobject.IO_ERR,
                self._progress)

        return self._blocker

    def detach(self, blocker):
        status = self._child.wait()
        if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
            msg = _('* failed to build;')
            self.emit('verbose', msg)
            return None
        else:
            msg = _('* done;')
            self.emit('verbose', msg)

        # XXX remove outdated cache values
        # pylint: disable-msg=W0212
        root_iface = iface_cache.get_interface(self._src_uri)
        for feed in root_iface.feeds:
            del iface_cache._interfaces[feed.uri]
        del iface_cache._interfaces[root_iface.uri]

        return []

    def _progress(self, stdout, condition):
        if not (condition & (gobject.IO_HUP | gobject.IO_ERR)):
            self.emit('verbose', stdout.readline().rstrip())
            return True
        self._blocker.trigger()
        return False


class _Handler(Handler):

    def __init__(self, confirm_import_feed_cb, report_error_cb):
        Handler.__init__(self)
        self._confirm_import_feed_cb = confirm_import_feed_cb
        self._report_error_cb = report_error_cb
        self._confirm_keys = None
        self._confirmed = None

    def is_confirming(self):
        return self._confirm_keys is not None

    def accept(self, key):
        if not self.is_confirming():
            logger.warning('key_confirm was not sent')
            return
        from zeroinstall.injector import trust
        trust.trust_db.trust_key(key.fingerprint, key.domain)
        self._confirm_next()

    def deny(self):
        if not self.is_confirming():
            logger.warning('key_confirm was not sent')
            return
        self._confirm_stop()

    def report_error(self, e, trace=None):
        self._report_error_cb(e, trace)

    @tasks.async
    def confirm_import_feed(self, pending, gpg_sigs):
        from zeroinstall.injector import trust

        domain = trust.domain_from_url(pending.url)
        self._confirm_keys = []
        for sig in gpg_sigs.keys():
            self._confirm_keys.append(_Key(sig, domain))

        self._confirmed = tasks.Blocker('confirm_import_feed')
        self._confirm_next()

        yield [self._confirmed]
        tasks.check([self._confirmed])

    def _confirm_next(self):
        if self._confirm_keys:
            self._confirm_import_feed_cb(self._confirm_keys.pop())
        else:
            self._confirm_stop()

    def _confirm_stop(self):
        self._confirmed.trigger()
        self._confirm_keys = None


class _Key(object):

    def __init__(self, gpg_sig, domain):
        self.domain = '' + domain
        self.fingerprint = '' + gpg_sig.fingerprint

        detail = {}
        for i in gpg_sig.get_details():
            detail[i[0]] = i[1:]

        if 'uid' in detail:
            self.user_id = detail['uid'][8]
        elif 'pub' in detail:
            self.user_id = detail['pub'][8]
        else:
            logger.warning('Can not get gpg details, ' \
                    'perhaps gnupg was not installed')
            self.user_id = gpg_sig.fingerprint


def _name(uri):
    if uri.endswith('saccharin.tmp'):
        return 'activity.info'
    else:
        return www.parse_name(uri)
