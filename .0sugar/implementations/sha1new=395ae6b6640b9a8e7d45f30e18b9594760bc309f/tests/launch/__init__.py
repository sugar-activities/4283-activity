import os
import sys
import shutil
import signal
import logging
import unittest
import urlparse
import traceback
import BaseHTTPServer

sys.path.insert(0, '..')

from zeroinstall import support
from zeroinstall.support import basedir
from zeroinstall.injector import iface_cache
from zeroinstall.injector import download
from zeroinstall.injector import model
from zeroinstall.injector import fetch
from zeroinstall.injector import gpg
from zeroinstall.injector.policy import Policy

from zerosugar.util import www
from zerosugar.launcher import synthesis


_ENVS = {'GNUPGHOME': 'gnupg',
         'XDG_CONFIG_HOME': 'config',
         'XDG_CACHE_HOME': 'cache',
         'XDG_CACHE_DIRS': 'var'}

_ROOT = os.path.join(os.path.dirname(__file__), '.test')
_SERVER = ('localhost', 8000)
HTTP = 'http://localhost:8000/'

fetch.DEFAULT_KEY_LOOKUP_SERVER = 'http://localhost:8000/key-info'
www.IFACE_COMPILE = 'http://localhost:8000/files/0compile.xml'

_next_GET = None


class TestSaccharin(unittest.TestCase):

    def setUp(self):
        www.HTTP_ROOT = '<HTTP_ROOT>'
        www.REPO_ROOT = '<REPO_ROOT>'

        for name, path in _ENVS.items():
            os.environ[name] = os.path.join(_ROOT, path)
        if os.path.exists(os.environ['XDG_CACHE_HOME']):
            support.ro_rmtree(os.environ['XDG_CACHE_HOME'])
        shutil.rmtree(_ROOT, ignore_errors=True)
        for name, path in _ENVS.items():
            os.makedirs(os.environ[name], mode=0700)

        reload(basedir)
        assert basedir.xdg_config_home == os.environ['XDG_CONFIG_HOME']
        iface_cache.iface_cache.__init__()
        download._downloads = {}

        logger = logging.getLogger()
        for i in logger.handlers:
            logger.removeHandler(i)
        logging.basicConfig(
                filename=os.path.join(_ROOT, 'debug.log'),
                level=logging.DEBUG)

        self.logger = logging.getLogger('test')

        policy = Policy('')
        policy.network_use = model.network_full
        policy.freshness = 60
        policy.save_config()

        self._child = None

    def tearDown(self):
        self._stop_httpd()

    def _stop_httpd(self):
		if self._child is not None:
			os.kill(self._child, signal.SIGTERM)
			os.waitpid(self._child, 0)
			self._child = None

    def httpd(self, files):
        self._stop_httpd()

        server = BaseHTTPServer.HTTPServer(_SERVER, _Handler)

        self._child = os.fork()
        if self._child:
            return

        log = file(os.path.join(_ROOT, 'httpd.log'), 'w')
        sys.stdout = log
        sys.stderr = log

        try:
            global _next_GET
            for _next_GET in files:
                if isinstance(_next_GET, str):
                    _next_GET = [_next_GET]
                while _next_GET:
                    server.handle_request()
                    log.flush()
            os._exit(0)
        except:
            traceback.print_exc()
            os._exit(1)


class _Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse.urlparse(self.path).path.lstrip('/')

        if path not in _next_GET:
            self.send_error(404, "Expected %s; got %s" % (_next_GET, path))
            _next_GET.pop()
        else:
            _next_GET.remove(path)
            if path.startswith('key-info/'):
                self.send_response(200)
                self.end_headers()
                self.wfile.write('<key-lookup/>')
                self.wfile.close()
            elif os.path.exists(path):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(file(path).read())
                self.wfile.close()
            else:
                self.send_error(404, "Missing: %s" % path)
