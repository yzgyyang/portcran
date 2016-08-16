#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

from abc import ABCMeta, abstractmethod
from itertools import groupby
from math import ceil, floor
from operator import itemgetter
from os import getuid
from pwd import getpwuid
from re import match
from socket import gethostname
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

class Platform(object):
    _passwd = getpwuid(getuid())

    address = "%s@%s" % (_passwd.pw_name, gethostname())

    fullname = _passwd.pw_gecos

    pagewidth = 80

    tabwidth = 8

class Stream(object):
    def __init__(self, objects):
        self._objects = list(objects)
        self.line = 1

    @property
    def current(self):
        return self._objects[self.line - 1]

    @property
    def has_current(self):
        return self.line != -1

    def next(self, no_raise=False):
        if 0 <= self.line < len(self._objects):
            self.line += 1
            return True
        self.line = -1
        return False

    def take_until(self, condition):
        while self.next(no_raise=True) and not condition(self.current):
            yield self.current

class PortValue(object):
    __metaclass__ = ABCMeta

    def __init__(self, section, order=1):
        self.order = order
        self.section = section

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())

    def __lt__(self, other):
        return self.__key() < other.__key()

    def __key(self):
        return (self.section, self.order)

    @abstractmethod
    def generate(self, value):
        raise NotImplemented()

class PortVariable(PortValue):
    def __init__(self, section, order=1, name=None):
        super(PortVariable, self).__init__(section, order)
        self.name = name

    def __get__(self, obj, objtype=None):
        try:
            return obj._values[self]
        except KeyError:
            raise PortException("Port: port variable not set: %s" % self.name)

    def __set__(self, obj, value):
        obj._values[self] = value

    def generate(self, value):
        return (self.name, (value,) if isinstance(value, (str, unicode)) else value)

class PortObject(PortValue):
    def __init__(self, section, factory):
        super(PortObject, self).__init__(section)
        self.factory = factory

    def __get__(self, obj, objtype=None):
        if self not in obj._values:
            obj._values[self] = self.factory()
        return obj._values[self]

    def __set__(self, obj, value):
        raise PortException("Port: cannot set value for port variable: %s" % self.name)

    def generate(self, value):
        return value.generate()

class PortLicense(object):
    def generate(self):
        return ("LICENSE", ())

class PortDepends(object):
    def generate(self):
        return ("RUN_DEPENDS", ())

class PortUses(object):
    def __init__(self):
        self._uses = {}

    def add(self, name, args=()):
        if name not in self._uses:
            self._uses[name] = []
        if isinstance(args, (str, unicode)):
            self._uses[name].append(args)
        else:
            self._uses[name].extend(args)

    def generate(self):
        return ("USES", (k + (":" + ",".join(sorted(v)) if len(v) else "")  for k, v in sorted(self._uses.items(), itemgetter(0))))

class PortException(Exception):
    pass

class Port(object):
    _values = {}

    name = PortVariable(1, 1, "PORTNAME")
    version = PortVariable(1, 4, "DISTVERSION")
    categories = PortVariable(1, 8, "CATEGORIES")

    maintainer = PortVariable(2, 1, "MAINTAINER")
    comment = PortVariable(2, 2, "COMMENT")

    license = PortObject(3, PortLicense)

    depends = PortObject(4, PortDepends)

    uses = PortObject(5, PortUses)

    def __init__(self, name):
        self.name = name
        self.maintainer = Platform.address

    def generate(self):
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        return makefile.getvalue()

    @staticmethod
    def _gen_footer(makefile):
        makefile.write("\n.include <bsd.port.mk>\n")

    @staticmethod
    def _gen_header(makefile):
        makefile.writelines((
            "# Created by: %s <%s>\n" % (Platform.fullname, Platform.address),
            "# $FreeBSD$\n",
        ))

    def _gen_sections(self, makefile):
        items = list(self._values.items())
        items.sort(key=lambda i: i[0])
        for section, values in groupby(items, lambda i: i[0].section):
            values = [v[0].generate(v[1]) for v in values]
            tabs = max(2, int(ceil(max(len(n[0]) for n in values) + 1.0) / Platform.tabwidth))
            makefile.write("\n")
            for name, value in values:
                makefile.write("%s=%s" % (name, "\t" * (tabs - int(floor((len(name) + 1.0) / Platform.tabwidth)))))
                width = tabs * Platform.tabwidth
                firstline = True
                for v in value:
                    if not firstline and width + len(v) > Platform.pagewidth:
                        makefile.write(" \\\n")
                    firstline = False
                    makefile.write(v)
                makefile.write("\n")

    @staticmethod
    def _get_tabs(names):
        return

class CranPort(Port):
    def __init__(self, name):
        super(CranPort, self).__init__(name)
        self.categories = ("math",)
        self.uses.add("cran", "auto-plist")

ignored_keys = [
        "Date",
        "Authors@R",
        "ByteCompile",
        "LazyLoad",
        "LazyData",
        "Author",
        "Maintainer",
        "Repository",
        "Repository/R-Forge/Project",
        "Repository/R-Forge/Revision",
        "Repository/R-Forge/DateTimeStamp",
        "Date/Publication",
        "Packaged",
    ]

def make_cran_port(name):
    port = CranPort(name)
    with open("test/car/DESCRIPTION", "rU") as package:
        descr = Stream(l.rstrip('\n') for l in package.readlines())
    while descr.has_current:
        line = descr.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + l.strip() for l in descr.take_until(lambda l: match("^[a-zA-Z/@]+:", l)))
        if key == "Package":
            if port.name != value:
                raise PortException("CRAN: package name (%s) does not match port name (%s)" % (value, port.name))
        elif key == "Version":
            port.version = value
        elif key == "Title":
            port.comment = value
        elif key == "Depends":
            pass
        elif key == "Imports":
            pass
        elif key == "Suggests":
            pass
        elif key == "Description":
            pass
        elif key == "License":
            pass
        elif key == "URL":
            pass
        elif key == "NeedsCompilation":
            port.uses.add("cran", "compiles")
        elif key not in ignored_keys:
            raise PortException("CRAN: package key %s unknown at line %s" % (key, line))
    return port

port = make_cran_port("car")
print(port.generate())
