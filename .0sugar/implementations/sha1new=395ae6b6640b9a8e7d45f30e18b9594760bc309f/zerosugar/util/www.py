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
import sys
import traceback
import subprocess
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr

from zerosugar.util.logger import logger


LIST_SEPARATOR = ','

FEEDS_ROOT = 'http://services.sugarlabs.org'
BUNDLES_ROOT = 'http://download.sugarlabs.org/services'

FEED = 'service.xml'
REVISION = 'revision'

def url(service, file=None):
    if service.startswith('http://'):
        return service

    name = service.split('/')
    if len(name) > 1:
        service = name[0]
        if file is None:
            file = name[1] + '.xml'
    else:
        service = name[0]
        if file is None:
            file = FEED

    if file == FEED:
        return '%s/%s' % (FEEDS_ROOT, service)
    elif file.endswith('.xml'):
        return '%s/%s/%s' % (FEEDS_ROOT, service, file)
    else:
        return '%s/%s/%s' % (BUNDLES_ROOT, service, file)

IFACE_SACCHARIN = url('saccharin')
IFACE_INJECTOR = url('zeroinstall-injector')
IFACE_COMPILE = url('0compile')

XMLNS = 'http://zero-install.sourceforge.net/2004/injector/interface'
XMLNS_COMPILE = 'http://zero-install.sourceforge.net/2006/namespaces/0compile'
XMLNS_SUGAR = url('saccharin', 'namespaces/0sugar')

ATTR_COMMIT = '%s commit' % XMLNS_SUGAR
ATTR_SLOT = '%s slot' % XMLNS_SUGAR
ATTR_COMPILE_COMMAND = '%s command' % XMLNS_COMPILE
ATTR_COMPILE_INCLUDE = '%s include-binary' % XMLNS_COMPILE


def header(args={'uri': None,
                 'name': '<name>',
                 'summary': '<summary>',
                 'description': '<description>',
                 'homepage': '<homepage>',
                 'icon': None,
                 'icon_type': None,
                 'category': None,
                 }):
    for i in args.keys():
        args[i] = escape(str(args[i] or ''))

    args.update({'xmlns': XMLNS,
                 'xmlns_compile': XMLNS_COMPILE,
                 'xmlns_sugar': XMLNS_SUGAR})

    xml = """<?xml version="1.0" ?>
<?xml-stylesheet type='text/xsl' href='/interface.xsl'?>
<interface uri="%(uri)s"
           xmlns="%(xmlns)s"
           xmlns:compile="%(xmlns_compile)s"
           xmlns:sugar="%(xmlns_sugar)s">
    <name>%(name)s</name>
    <summary>%(summary)s</summary>
    <description>%(description)s</description>
    <homepage>%(homepage)s</homepage>""" % args

    if args.get('icon'):
        xml += """
    <icon href="%(icon)s" type="%(icon_type)s"/>""" % args

    if args.get('category'):
        xml += """
    <category>%(category)s</category>""" % args

    return xml

def package(args={'package': None,
                  'distro': None,
                  'main': None}):
    for i in args.keys():
        args[i] = quoteattr(str(args[i] or ''))

    xml = """
    <package-implementation package=%(package)s""" % args
    if args.get('main') != '""':
        xml += ' main=%(main)s' % args
    if args.get('distro') != '""':
        xml += ' distributions=%(distro)s' % args
    return xml + '/>'

def sibling(args={'interface': None}):
    for i in args.keys():
        args[i] = quoteattr(str(args[i] or ''))

    xml = """
    <sugar:sibling interface=%(interface)s/>""" % args

    return xml

def impl_header(args={'id': '.',
                      'version': '0',
                      'main': '',
                      'released': '',
                      'stability': None,
                      'arch': '*-*',
                      'license': '',
                      'compile': None,
                      'commit': None,
                      'slot': None,
                      }):
    for i in args.keys():
        args[i] = quoteattr(str(args[i] or ''))

    xml = """
    <implementation id=%(id)s
                    version=%(version)s
                    released=%(released)s
                    arch=%(arch)s
                    license=%(license)s""" % args
    if args.get('stability') != '""':
        xml += """
                    stability=%(stability)s""" % args
    if args.get('main') != '""':
        xml += """
                    main=%(main)s""" % args
    if args.get('compile') != '""':
        xml += """
                    compile:command=%(compile)s""" % args
    if args.get('commit') != '""':
        xml += """
                    sugar:commit=%(commit)s""" % args
    if args.get('slot') != '""':
        xml += """
                    sugar:slot=%(slot)s""" % args

    return xml + '>'

def archive(args):
    for i in args.keys():
        args[i] = quoteattr(str(args[i] or ''))

    result = """
        <archive href=%(href)s size=%(size)s""" % args
    if args.get('extract') != '""':
        result += ' extract=%(extract)s' % args

    return result + '/>'

def binding(args):
    for i in args.keys():
        args[i] = quoteattr(str(args[i] or ''))

    xml = """
        <environment name=%(name)s mode=%(mode)s insert=%(insert)s""" % args
    if args.get('default') != '""':
        xml += ' default=%(default)s' % args
    xml += '/>'

    return xml

def impl_footer():
    return """
    </implementation>"""

def footer():
    return """
</interface>
"""

def parse_name(url, default=None):
    if url.startswith(FEEDS_ROOT):
        if url.endswith('.xml'):
            sub = os.path.basename(url)[:-4]
            return os.path.basename(os.path.dirname(url)) + '/' + sub
        else:
            return os.path.basename(url.rstrip('/'))
    elif default is None:
        return url
    else:
        return default

def parse_list(str):
    if not str:
        return []

    parts = []
    brackets = {('(', ')'): 0,
                ('[', ']'): 0,
                ('"', '"'): 0}
    str = str.replace("\n", LIST_SEPARATOR).strip()
    i = 0

    while i < len(str):
        if not max(brackets.values()) and str[i] == LIST_SEPARATOR:
            parts.append(str[:i].strip())
            str = str[i + 1:]
            i = 0
        else:
            for key in brackets.keys():
                left, right = key
                if str[i] == left:
                    brackets[key] += 1
                    break
                elif str[i] == right:
                    brackets[key] -= 1
                    break
            i += 1

    if str.strip():
        parts.append(str.strip())

    return parts

def parse_condition(condition):
    not_before = None
    before = None

    match = re.split('(>=|<|~)\s*([0-9.]+)', condition)
    while len(match) >= 3:
        if match[1] == '>=':
            not_before = match[2]
        elif match[1] == '<':
            before = match[2]
        elif match[1] == '~':
            not_before = match[2]
            parts = match[2].split('.')
            before = '.'.join(parts[:-1] + [str(int(parts[-1]) + 1)])
        del match[:3]

    if match and match[0].strip():
        print '! cannot parse "%s" restriction in "%s", it should be ' \
                'in format "(>=|<|~) <version>"' % (condition, match)
        exit(1)

    return not_before, before

def parse_requires(config, section):
    requires = []

    def parse(requires_str, optional):
        for dep in parse_list(requires_str):
            bindings = []

            binding_str = re.search('\(([^)]+)\)', dep)
            if binding_str is not None:
                bindings = parse_bindings(binding_str.groups()[0])
                dep = dep[:binding_str.start()]

            parts = dep.split()
            if not parts:
                logger.warning('Can not get requires from "%s" string.', dep)
                continue

            dep_name = parts[0]
            not_before, before = parse_condition(' '.join(parts[1:]))

            requires.append((dep_name, optional, not_before, before, bindings))

    if config.has_option(section, 'requires'):
        parse(config.get(section, 'requires'), False)
    if config.has_option(section, 'suggests'):
        parse(config.get(section, 'suggests'), True)

    return requires

def parse_bindings(binds_str):
    bindings = []

    def parse(bind):
        parts = bind.split()
        if not parts:
            return

        entry = {}
        if parts[0].lower() in ['prepend', 'append', 'replace']:
            entry['mode'] = parts[0].lower()
            parts = parts[1:]
        else:
            entry['mode'] = 'prepend'
        if len(parts) > 1:
            entry['insert'] = parts.pop()
        entry['name'] = parts[0]

        bindings.append(entry)

    for bind in parse_list(binds_str):
        parse(bind)

    return bindings
