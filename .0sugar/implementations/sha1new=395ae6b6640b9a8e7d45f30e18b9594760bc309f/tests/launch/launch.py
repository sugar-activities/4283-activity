#!/usr/bin/env python

import time
from os.path import abspath

import gtk
import gobject

from __init__ import *
from zerosugar.launcher.synthesis import Flask


FEED_MAIN = '.test/refresh.xml'
FEED_INJECTOR = 'files/0compile.xml'
FEED_SACCHARIN = '.test/dependency.xml'


class TestLaunch(TestSaccharin):

    def testInitialStartup(self):
        self.init()

    def testNextFastStartup(self):
        self.init()

        flask = self.launch([])
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

    def testNextSlowStartup(self):
        self.init()

        time.sleep(3)
        self.set_freshness(1)

        flask = self.launch([])
        self.assertEqual(True, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

        self.set_freshness(3)

        flask = self.refresh()
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(3, flask.processed)
        self.assertEqual(0, flask.skipped)

        self.set_freshness(60)

        flask = self.launch([])
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

    def testNonCriticalUpdate(self):
        self.init()

        shutil.copy('files/refresh-2.xml', '.test/refresh.xml')
        shutil.copy('files/dependency-2.xml', '.test/dependency.xml')

        time.sleep(3)
        self.set_freshness(1)

        flask = self.launch([])
        self.assertEqual(True, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

        self.set_freshness(3)

        flask = self.refresh()
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(3, flask.processed)
        self.assertEqual(0, flask.skipped)

        self.set_freshness(60)

        flask = self.launch([])
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

    def testCriticalUpdate(self):
        self.init()

        shutil.copy('files/refresh-3.xml', '.test/refresh.xml')
        shutil.copy('files/dependency-3.xml', '.test/dependency.xml')

        time.sleep(3)
        self.set_freshness(1)

        flask = self.launch([])
        self.assertEqual(True, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(3, flask.skipped)

        self.set_freshness(3)

        flask = self.refresh()
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(3, flask.processed)
        self.assertEqual(0, flask.skipped)

        self.set_freshness(60)

        flask = self.launch(['files/Dependency-2.tgz', 'files/Refresh-2.tgz'])
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(2, flask.processed)
        self.assertEqual(1, flask.skipped)

    def init(self):
        shutil.copy('files/refresh-1.xml', '.test/refresh.xml')
        shutil.copy('files/dependency-1.xml', '.test/dependency.xml')

        flask = self.launch([
                FEED_INJECTOR,
                'files/25CE480645A8CA07.gpg',
                'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                'files/0compile-0.18.tar.bz2',
                FEED_SACCHARIN,
                'files/Dependency.tgz',
                FEED_MAIN,
                'files/Refresh-1.tgz',
                ])

        self.assertEqual(False, flask.is_stale())
        self.assertEqual(3, flask.processed)
        self.assertEqual(0, flask.skipped)

    def need_download(self, url):
        policy = Policy(HTTP + url)
        return policy.need_download()

    def launch(self, files):
        self.httpd(files)

        flask = Flask()
        status = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('key_confirm',
                lambda sender, key: sender.accept(key))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        def pull():
            flask.pull([HTTP + FEED_MAIN,
                        HTTP + FEED_SACCHARIN,
                        HTTP + FEED_INJECTOR,
                        ])
        gobject.idle_add(pull)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + FEED_MAIN, flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(False, self.need_download(FEED_MAIN))
        self.assertEqual(False, self.need_download(FEED_INJECTOR))
        self.assertEqual(False, self.need_download(FEED_SACCHARIN))

        return flask

    def set_freshness(self, freshness):
        policy = Policy('')
        policy.network_use = model.network_minimal
        policy.freshness = freshness
        policy.save_config()

    def refresh(self):
        self.httpd([FEED_INJECTOR,
                    FEED_SACCHARIN,
                    FEED_MAIN,
                    ])

        flask = Flask()
        status = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        def refresh():
            flask.refresh([HTTP + FEED_MAIN,
                           HTTP + FEED_SACCHARIN,
                           HTTP + FEED_INJECTOR,
                           ])
        gobject.idle_add(refresh)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(True, flask.policy.solver.ready)

        return flask


if __name__ == '__main__':
    unittest.main()
