#!/usr/bin/env python

import abc
import getpass
import re
import socket
import sys

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
    __metaclass__ = abc.ABCMeta

    def __init__(self, section, order=1):
        self.order = order
        self.section = section

    def __cmp__(self, other):
        if self.section < other.section:
            return -1
        if self.section > other.section:
            return 1
        if self.order < other.order:
            return -1
        if self.order > other.order:
            return 1
        return 0

    @abc.abstractmethod
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
        return (self.name, (value,))

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
    def generate(self):
        return ("USES", ())

class PortException(Exception):
    pass

class Port(object):
    _values = {}

    name = PortVariable(1, 1, "PORTNAME")
    version = PortVariable(1, 2, "DISTVERSION")
    categories = PortVariable(1, 3, "CATEGORIES")

    maintainer = PortVariable(2, 1, "MAINTAINER")
    comment = PortVariable(2, 2, "COMMENT")

    license = PortObject(3, PortLicense)

    depends = PortObject(4, PortDepends)

    uses = PortObject(5, PortUses)

    def __init__(self, name):
        self.name = name
        self.maintainer = "%s@%s" % (getpass.getuser(), socket.gethostname())

    def generate(self):
        print "$FreeBSD$"
        items = list(self._values.items())
        items.sort(key=lambda i: i[0])
        section = 0
        for item in items:
            portvalue = item[0]
            if portvalue.section != section:
                print
                section = portvalue.section
            print portvalue.generate(item[1])

class CranPort(Port):
    def __init__(self, name):
        super(CranPort, self).__init__(name)
        self.categories = "math"

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
    with open("/tmp/1/car/DESCRIPTION", "rU") as package:
        descr = Stream(l.rstrip('\n') for l in package.readlines())
    while descr.has_current:
        line = descr.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + l.strip() for l in descr.take_until(lambda l: re.match("^[a-zA-Z/@]+:", l)))
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
            pass
        elif key not in ignored_keys:
            raise PortException("CRAN: package key %s unknown at line %s" % (key, line))
    return port

port = make_cran_port("car")
port.generate()
