#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from itertools import groupby
from math import ceil, floor
from os import getuid
from pwd import getpwuid
from re import match
from socket import gethostname
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

class Orderable(object):
    __metaclass__ = ABCMeta

    def __eq__(self, other):
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __lt__(self, other):
        return self._key() < other._key()

    @abstractmethod
    def _key(self):
        raise NotImplemented()

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

class PortValue(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, section, order=1):
        self.order = order
        self.section = section

    def _key(self):
        return (self.section, self.order)

    @abstractmethod
    def generate(self, value):
        raise NotImplemented()

class PortVariable(PortValue):
    def __init__(self, section, order=1, name=None):
        super(PortVariable, self).__init__(section, order)
        self.name = name

    def __get__(self, obj, objtype=None):
        value = obj.uses.get_variable(self.name, obj._values[self] if self in obj._values else None)
        if value is None:
            raise PortException("Port: port variable not set: %s" % self.name)
        return value

    def __set__(self, obj, value):
        obj._values[self] = value

    def generate(self, value):
        return ((self.name, (value,) if isinstance(value, (str, unicode)) else value),)

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
        return (("LICENSE", ()),)

class Dependency(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, port):
        self.port = port

    @abstractmethod
    def __str__(self):
        raise NotImplemented()

    def _key(self):
        return self.port.name

class PortDependency(Dependency):
    def __init__(self, port, condition=">0"):
        self.port = port
        self.condition = condition

    def __str__(self):
        return "%s%s:%s" % (self.port.pkgname, self.condition, self.port.origin)

class PortDepends(object):
    class Depends(object):
        def __init__(self, depends):
            self._depends = depends

        def add(self, dependency):
            self._depends.add(dependency)

        def generate(self):
            return (str(d) for d in sorted(self._depends))

    def __init__(self):
        self._depends = OrderedDict()
        self.run = self._make_depends("RUN_DEPENDS")
        self.test = self._make_depends("TEST_DEPENDS")

    def _make_depends(self, name):
        depends = set()
        self._depends[name] = depends
        return PortDepends.Depends(depends)

    def generate(self):
        return ((k, (str(d) + "\n" for d in sorted(v))) for k, v in self._depends.items() if len(v))

class Uses(Orderable):
    def __init__(self, name):
        self._args = set()
        self.name = name

    def __str__(self):
        return self.name + (":" + ",".join(sorted(self._args)) if len(self._args) else "")

    def _key(self):
        return self.name

    def add(self, arg):
        self._args.add(arg)

    def get_variable(self, name):
        return None

class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self):
        super(Cran, self).__init__("cran")

    @staticmethod
    def get_variable(name):
        if name == "PKGNAMEPREFIX":
            return Cran.PKGNAMEPREFIX
        return None

class PortUses(object):
    def __init__(self):
        self._uses = {}

    def __call__(self, uses):
        if uses not in self._uses:
            self._uses[uses] = uses()
        return self._uses[uses]

    def get_variable(self, name, value):
        values = [v for v in (u.get_variable(name) for u in self._uses.values()) if v is not None]
        if len(values) > 1:
            raise PortException("PortUses: multiple uses define value for variable '%s'" % name)
        return values[0] if len(values) else value

    def generate(self):
        return (("USES", (str(u) for u in sorted(self._uses.values()))),)

class PortException(Exception):
    pass

class Port(object):
    portname = PortVariable(1, 1, "PORTNAME")
    distversion = PortVariable(1, 4, "DISTVERSION")
    categories = PortVariable(1, 8, "CATEGORIES")
    pkgnameprefix = PortVariable(1, 12, "PKGNAMEPREFIX")

    maintainer = PortVariable(2, 1, "MAINTAINER")
    comment = PortVariable(2, 2, "COMMENT")

    license = PortObject(3, PortLicense)

    depends = PortObject(4, PortDepends)

    uses = PortObject(5, PortUses)

    def __init__(self, name):
        self._values = {}
        self.maintainer = Platform.address
        self.name = name

    @property
    def origin(self):
        return "%s/%s" % (self.categories[0], self.pkgname)

    @property
    def pkgname(self):
        return "%s%s" % (self.pkgnameprefix, self.portname)

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
            values = [u for v in values for u in v[0].generate(v[1])]
            tabs = max(2, int(ceil(max(len(n[0]) for n in values) + 1.0) / Platform.tabwidth))
            makefile.write("\n")
            for name, value in values:
                makefile.write("%s=%s" % (name, "\t" * (tabs - int(floor((len(name) + 1.0) / Platform.tabwidth)))))
                width = tabs * Platform.tabwidth
                firstline = True
                for v in value:
                    nextline = v[-1] == "\n"
                    v = v.rstrip("\n")
                    if not firstline:
                        if width == -1 or width + len(v) + 1 > Platform.pagewidth:
                            makefile.write(" \\\n%s" % ("\t" * tabs))
                            width = tabs * Platform.tabwidth
                        else:
                            makefile.write(" ")
                            width += 1
                    firstline = False
                    makefile.write(v)
                    if nextline:
                        width = -1
                    else:
                        width += len(v)
                makefile.write("\n")

    @staticmethod
    def _get_tabs(names):
        return

    def generate(self):
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        return makefile.getvalue()

class CranPort(Port):
    def __init__(self, name):
        super(CranPort, self).__init__(Cran.PKGNAMEPREFIX + name)
        self.categories = ("math",)
        self.portname = name
        self.uses(Cran).add("auto-plist")

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

internal_packages = [
    "KernSmooth",
    "MASS",
    "Matrix",
    "boot",
    "class",
    "cluster",
    "codetools",
    "compiler",
    "datasets",
    "foreign",
    "grDevices",
    "graphics",
    "grid",
    "lattice",
    "methods",
    "mgcv",
    "nlme",
    "nnet",
    "parallel",
    "rpart",
    "spatial",
    "splines",
    "stats",
    "stats4",
    "survival",
    "tcltk",
    "tools",
    "utils",
]

def add_dependency(depends, value):
    for cran in value.split(","):
        cran = match(r"^\s*(\w+)(?:\s*\((.*)\))?\s*$", cran)
        name = cran.group(1).strip()
        if name not in internal_packages:
            condition = cran.group(2).replace("-", ".").replace(" ", "") if cran.group(2) else ">0"
            depends.add(PortDependency(CranPort(name), condition))

def make_cran_port(name):
    port = CranPort(name)
    with open("test/car/DESCRIPTION", "rU") as package:
        descr = Stream(l.rstrip('\n') for l in package.readlines())
    while descr.has_current:
        line = descr.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + l.strip() for l in descr.take_until(lambda l: match("^[a-zA-Z/@]+:", l)))
        if key == "Package":
            if port.name != Cran.PKGNAMEPREFIX + value:
                raise PortException("CRAN: package name (%s) does not match port name (%s)" % (value, port.name))
        elif key == "Version":
            port.distversion = value
        elif key == "Title":
            port.comment = value
        elif key == "Depends":
            pass
        elif key == "Imports":
            add_dependency(port.depends.run, value)
        elif key == "Suggests":
            add_dependency(port.depends.test, value)
        elif key == "Description":
            pass
        elif key == "License":
            pass
        elif key == "URL":
            pass
        elif key == "NeedsCompilation":
            port.uses(Cran).add("compiles")
        elif key not in ignored_keys:
            raise PortException("CRAN: package key %s unknown at line %s" % (key, line))
    return port

port = make_cran_port("car")
print(port.generate())
