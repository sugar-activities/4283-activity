#!/usr/bin/env python

import time
from os.path import abspath

import gtk
import gobject

from __init__ import *
from zeroinstall.injector.iface_cache import iface_cache
from zerosugar.launcher.synthesis import Flask


class TestSynthesis(TestSaccharin):

    def testWrongFeed(self):
        self.httpd(['WrongFeed'])

        flask = Flask()
        status = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull(HTTP + 'WrongFeed')
        gtk.main()

        self.assertEqual([False], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + 'WrongFeed', flask.policy.root)
        self.assertEqual(False, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testDownload(self):
        self.httpd(['files/download.xml',
                   'files/25CE480645A8CA07.gpg',
                   'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                   'files/HelloWorld.tgz'])

        flask = Flask()
        status = []
        progress = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('progress',
                lambda sender, fraction: progress.append(fraction))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.accept(key)))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull(HTTP + 'files/download.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertNotEqual([], keys)
        self.assertNotEqual([], progress)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testDenyKeyConfirm(self):
        self.httpd(['files/download.xml',
                   'files/25CE480645A8CA07.gpg'])

        flask = Flask()
        status = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.deny()))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull(HTTP + 'files/download.xml')
        gtk.main()

        self.assertEqual([False], status)
        self.assertEqual(False, flask.active)
        self.assertNotEqual([], keys)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(False, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testLocalRequires(self):
        self.httpd([['files/dependency.xml', 'files/download.xml',
                     'files/25CE480645A8CA07.gpg',
                     'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07'],
                   ['files/Dependency.tgz', 'files/HelloWorld.tgz']])

        flask = Flask()
        status = []
        progress = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('progress',
                lambda sender, fraction: progress.append(fraction))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.accept(key)))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull('files/local-requires.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertNotEqual([], keys)
        self.assertNotEqual([], progress)
        self.assertEqual(abspath('files/local-requires.xml'), flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testWrongLocalRequires(self):
        flask = Flask()
        status = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('progress',
                lambda sender, fraction: progress.append(fraction))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.accept(key)))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        gobject.idle_add(
                lambda: flask.pull('files/bad.xml'))
        gtk.main()

        self.assertEqual([False], status)
        self.assertEqual(False, flask.active)
        self.assertEqual([], keys)
        self.assertEqual(None, flask.policy)
        self.assertEqual(0, flask.processed)
        self.assertEqual(1, flask.skipped)

    def testLocalRequiresWithCompile(self):
        self.httpd([['files/dependency.xml', 'files/source.xml',
                     'files/25CE480645A8CA07.gpg',
                     'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07'],
                   'files/0compile.xml',
                   'files/0compile-0.18.tar.bz2',
                   'files/hello-1.3.tar.gz',
                   'files/Dependency.tgz'])

        flask = Flask()
        status = []
        progress = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('progress',
                lambda sender, fraction: progress.append(fraction))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.accept(key)))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull('files/compile.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertNotEqual([], keys)
        self.assertNotEqual([], progress)
        self.assertEqual(abspath('files/compile.xml'), flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testRefresh(self):
        self.httpd(['.test/refresh.xml',
                    '.test/25CE480645A8CA07.gpg',
                    'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                    'files/Refresh-1.tgz',
                    '.test/refresh.xml',
                    ])

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

        shutil.copy('files/refresh-1.xml', '.test/refresh.xml')
        shutil.copy('files/25CE480645A8CA07.gpg', '.test/')
        flask.pull(HTTP + '.test/refresh.xml',
                network_use=model.network_minimal)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(HTTP + '.test/refresh.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)
        self.assertEqual('1', get_version(flask))

        status = []
        shutil.copy('files/refresh-2.xml', '.test/refresh.xml')
        gobject.idle_add(
                lambda: flask.refresh(HTTP + '.test/refresh.xml', freshness=10))
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(HTTP + '.test/refresh.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)
        self.assertEqual('2', get_version(flask))

    def testStale(self):
        self.httpd(['files/download.xml',
                    'files/25CE480645A8CA07.gpg',
                    'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                    'files/HelloWorld.tgz',
                    'files/download.xml',
                    'files/download.xml',
                    ])

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

        flask.pull(HTTP + 'files/download.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

        time.sleep(1)

        status = []
        def refresh():
            flask.refresh(HTTP + 'files/download.xml', freshness=10)
        gobject.idle_add(refresh)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

        time.sleep(3)

        policy = Policy(HTTP + 'files/download.xml')
        policy.freshness = 1
        policy.need_download()
        feed = [iface_cache.get_feed(i) for i in policy.solver.feeds_used][0]
        self.assertEqual(True, policy.is_stale(feed))

        status = []
        def refresh():
            flask.refresh(HTTP + 'files/download.xml', freshness=1)
        gobject.idle_add(refresh)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

        policy = Policy(HTTP + 'files/download.xml')
        policy.freshness = 3
        policy.need_download()
        feed = [iface_cache.get_feed(i) for i in policy.solver.feeds_used][0]
        self.assertEqual(False, policy.is_stale(feed))

    def testOfflineInitial(self):
        flask = Flask()
        status = []
        keys = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('key_confirm',
                lambda sender, key: (keys.append(key), sender.accept(key)))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        flask.pull(HTTP + 'files/download.xml')
        gtk.main()

        self.assertEqual([False], status)
        self.assertEqual(False, flask.active)
        self.assertEqual([], keys)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(False, flask.policy.solver.ready)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testOfflineTryReadyToUseFeeds(self):
        self.testDownload()

        flask = Flask()
        status = []

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        gobject.idle_add(
                lambda: flask.pull(HTTP + 'files/download.xml'))
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(False, flask.is_stale())
        self.assertEqual(0, flask.processed)
        self.assertEqual(1, flask.skipped)


    def testOutdatedUpdate(self):
        self.httpd(['.test/refresh.xml',
                    '.test/25CE480645A8CA07.gpg',
                    'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                    '.test/refresh.xml',
                    'files/Refresh-2.tgz',
                    ])

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

        shutil.copy('files/revision-2.xml', '.test/refresh.xml')
        shutil.copy('files/25CE480645A8CA07.gpg', '.test/')
        flask.refresh(HTTP + '.test/refresh.xml')
        #flask.pull(HTTP + '.test/refresh.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + '.test/refresh.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(True, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

        status = []
        shutil.copy('files/revision-1.xml', '.test/refresh.xml')
        flask.refresh(HTTP + '.test/refresh.xml')
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + '.test/refresh.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(True, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

        status = []
        def pull():
            flask.pull(HTTP + '.test/refresh.xml')
        gobject.idle_add(pull)
        gtk.main()

        self.assertEqual([True], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + '.test/refresh.xml', flask.policy.root)
        self.assertEqual(True, flask.policy.solver.ready)
        self.assertEqual(False, flask.policy.need_download())
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)

    def testInfiniteLoopOnFailDownloads(self):
        self.httpd(['files/download.xml',
                   'files/25CE480645A8CA07.gpg',
                   'key-info/key/EC37EA199F9ADC3328EE338625CE480645A8CA07',
                   'foo',
                   '.test/download.xml',
                   'bar',
                   '.test/download.xml',
                   'files/HelloWorld.tgz',
                   ])

        flask = Flask()

        flask.connect('finished',
                lambda sender: (status.append(True), gtk.main_quit()))
        flask.connect('cancelled',
                lambda sender: (status.append(False), gtk.main_quit()))
        flask.connect('key_confirm',
                lambda sender, key: sender.accept(key))
        flask.connect('verbose',
                lambda sender, message: self.logger.info(message))

        www.HTTP_ROOT = 'http://localhost:8000/files'
        www.REPO_ROOT = 'http://localhost:8000/.test'
        shutil.copy('files/download.xml', '.test/')

        status = []
        flask.pull(HTTP + 'files/download.xml')
        gtk.main()

        self.assertEqual([False], status)
        self.assertEqual(False, flask.active)
        self.assertEqual(HTTP + 'files/download.xml', flask.policy.root)
        self.assertEqual(1, flask.processed)
        self.assertEqual(0, flask.skipped)


def get_version(flask):
    impl = flask.policy.solver.selections.values()[0]
    return impl.get_version()


if __name__ == '__main__':
    unittest.main()
