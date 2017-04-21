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
import subprocess

from zeroinstall.injector import model
from zeroinstall.injector.iface_cache import iface_cache


def get_environ(policy, echo=False):
    environ = os.environ.copy()
    root_impl = _get_implementation(policy)

    def putenv(dep, impl):
        for bind in dep.bindings + impl.bindings:
            if not isinstance(bind, model.EnvironmentBinding) or \
                    impl.id.startswith('/') or impl.id.startswith('package:'):
                continue
            path = iface_cache.stores.lookup(impl.id)
            if path not in environ.get(bind.name, ''):
                environ[bind.name] = bind.get_value(path,
                        environ.get(bind.name, None))
                if echo:
                    print '%s=%s' % (bind.name, environ[bind.name])

    def process(impl):
        for dep in impl.requires:
            dep_iface = iface_cache.get_interface(dep.interface)
            dep_impl = policy.implementation.get(dep_iface)
            if dep_impl is not None:
                putenv(dep, dep_impl)
                process(dep_impl)

    putenv(root_impl, root_impl)
    process(root_impl)
    return environ

def get_main(policy):
    assert(policy.solver.ready)
    root_impl = _get_implementation(policy)
    root_path = policy.get_implementation_path(root_impl)
    return os.path.join(root_path, root_impl.main)

def _get_implementation(policy):
    # XXX why the same uri has two Interface objects
    # thus Policy.get_implementation() doesn't work
    for iface, impl in policy.implementation.items():
        if iface.uri == policy.root:
            return impl
    return None
