#!/usr/bin/env python3
from __future__ import absolute_import, division, print_function

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
    from io import StringIO  # type: ignore
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Union


class Orderable(object):
    __metaclass__ = ABCMeta

    def __eq__(self, other):
        # type: (object) -> bool
        assert isinstance(other, Orderable)
        return self.key() == other.key()

    def __hash__(self):
        # type: () -> int
        return hash(self.key())

    def __lt__(self, other):
        # type: (object) -> bool
        assert isinstance(other, Orderable)
        return self.key() < other.key()

    @abstractmethod
    def key(self):
        raise NotImplementedError()


class Platform(object):
    _passwd = getpwuid(getuid())

    address = "%s@%s" % (_passwd.pw_name, gethostname())

    full_name = _passwd.pw_gecos

    page_width = 80

    tab_width = 8


class Stream(object):
    def __init__(self, objects):
        # type: (Iterable[str]) -> None
        self._objects = list(objects)
        self.line = 1

    @property
    def current(self):
        # type: () -> str
        return self._objects[self.line - 1]

    @property
    def has_current(self):
        # type: () -> bool
        return self.line != -1

    def next(self):
        # type: () -> bool
        if 0 <= self.line < len(self._objects):
            self.line += 1
            return True
        self.line = -1
        return False

    def take_until(self, condition):
        # type: (Callable[[str], bool]) -> Iterable[str]
        while self.next() and not condition(self.current):
            yield self.current


class PortValue(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, section, order=1):
        # type: (int, int) -> None
        self.order = order
        self.section = section

    @abstractmethod
    def __get__(self, obj, objtype):
        # type: (Port, type) -> Any
        assert issubclass(objtype, Port)
        raise NotImplementedError()

    @abstractmethod
    def generate(self, value):
        # type: (Any) -> Iterable[Tuple[str, Iterable[str]]]
        raise NotImplementedError()

    def key(self):
        # type: () -> Tuple[int, int]
        return self.section, self.order


class PortVar(PortValue):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVar, self).__init__(section, order)
        self.name = name

    def __get__(self, obj, objtype):
        # type: (Port, type) -> Union[str, List[str]]
        assert issubclass(objtype, Port)
        value = obj.get_value(self) if obj.has_value(self) else None
        assert isinstance(value, str)
        value = obj.uses.get_variable(self.name, value)
        if value is None:
            raise PortException("Port: port variable not set: %s" % self.name)
        return value

    def __set__(self, obj, value):
        # type: (Port, Union[str, List[str]]) -> None
        obj.set_value(self, value)

    def generate(self, value):
        # type: (Union[str, List[str]]) -> Iterable[Tuple[str, Iterable[str]]]
        return (self.name, (value,) if isinstance(value, str) else value),  # type: ignore


class PortObj(PortValue):
    def __init__(self, section, factory):
        # type: (int, Callable[[], PortObject]) -> None
        super(PortObj, self).__init__(section)
        self.factory = factory

    def __get__(self, obj, objtype):
        # type: (Port, type) -> PortObject
        assert issubclass(objtype, Port)
        if not obj.has_value(self):
            obj.set_value(self, self.factory())
        value = obj.get_value(self)
        assert isinstance(value, PortObject)
        return value

    def generate(self, value):
        # type: (PortObject) -> Iterable[Tuple[str, Iterable[str]]]
        return value.generate()


class PortObject(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        raise NotImplementedError()


class PortLicense(PortObject):
    def __init__(self):
        # type: () -> None
        super(PortLicense, self).__init__()
        self._licenses = set()  # type: Set[str]

    def add(self, license_type):
        # type: (str) -> None
        self._licenses.add(license_type)

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        return ("LICENSE", sorted(self._licenses)),


class Dependency(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, port):
        # type: (Port) -> None
        self.port = port

    @abstractmethod
    def __str__(self):
        # type: () -> str
        raise NotImplementedError()

    def key(self):
        # type: () -> str
        return self.port.name


class PortDependency(Dependency):
    def __init__(self, port, condition=">0"):
        # type: (Port, str) -> None
        super(PortDependency, self).__init__(port)
        self.port = port
        self.condition = condition

    def __str__(self):
        # type: () -> str
        return "%s%s:%s" % (self.port.pkgname, self.condition, self.port.origin)


class PortDepends(PortObject):
    class Depends(object):
        def __init__(self, depends):
            # type: (Set[Dependency]) -> None
            self._depends = depends

        def add(self, dependency):
            # type: (Dependency) -> None
            self._depends.add(dependency)

        def generate(self):
            # type: () -> Iterable[str]
            return (str(d) for d in sorted(self._depends))

    def __init__(self):
        # type: () -> None
        super(PortDepends, self).__init__()
        self._depends = OrderedDict()  # type: Dict[str, Set[Dependency]]
        self.run = self._make_depends("RUN_DEPENDS")
        self.test = self._make_depends("TEST_DEPENDS")

    def _make_depends(self, name):
        # type: (str) -> PortDepends.Depends
        depends = set()  # type: Set[Dependency]
        self._depends[name] = depends
        return PortDepends.Depends(depends)

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        return ((k, (str(d) + "\n" for d in sorted(v)))
                for k, v in self._depends.items() if len(v))


class Uses(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        self._args = set()
        self.name = name

    def __str__(self):
        return self.name + (":" + ",".join(sorted(self._args)) if len(self._args) else "")

    def add(self, arg):
        self._args.add(arg)

    @abstractmethod
    def get_variable(self, name):
        raise NotImplementedError()

    def key(self):
        return self.name


class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self):
        super(Cran, self).__init__("cran")

    def get_variable(self, name):
        if name == "PKGNAMEPREFIX":
            return Cran.PKGNAMEPREFIX
        return None


class PortUses(PortObject):
    def __init__(self):
        # type: () -> None
        super(PortUses, self).__init__()
        self._uses = {}  # type: Dict[type, Uses]

    def __call__(self, uses):
        # type: (type) -> Uses
        if uses not in self._uses:
            self._uses[uses] = uses()
        return self._uses[uses]

    def get_variable(self, name, value):
        # type: (str, str) -> str
        values = [v for v in (u.get_variable(name) for u in self._uses.values()) if v is not None]
        if len(values) > 1:
            raise PortException("PortUses: multiple uses define value for variable '%s'" % name)
        return values[0] if len(values) else value

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        return ("USES", (str(u) for u in sorted(self._uses.values()))),


class PortException(Exception):
    pass


class Port(object):
    portname = PortVar(1, 1, "PORTNAME")
    distversion = PortVar(1, 4, "DISTVERSION")
    categories = PortVar(1, 8, "CATEGORIES")  # type: List[str]
    pkgnameprefix = PortVar(1, 12, "PKGNAMEPREFIX")

    maintainer = PortVar(2, 1, "MAINTAINER")  # type: str
    comment = PortVar(2, 2, "COMMENT")

    license = PortObj(3, PortLicense)  # type: PortLicense

    depends = PortObj(4, PortDepends)  # type: PortDepends

    uses = PortObj(5, PortUses)  # type: PortUses

    def __init__(self, name):
        # type: (str) -> None
        self._values = {}  # type: Dict[PortValue, Union[str, List[str], PortObject]]
        self.maintainer = Platform.address
        self.name = name

    @property
    def origin(self):
        # type: () -> str
        return "%s/%s" % (self.categories[0], self.pkgname)

    @property
    def pkgname(self):
        # type: () -> str
        return "%s%s" % (self.pkgnameprefix, self.portname)

    @staticmethod
    def _gen_footer(makefile):
        makefile.write("\n.include <bsd.port.mk>\n")

    @staticmethod
    def _gen_header(makefile):
        makefile.writelines((
            "# Created by: %s <%s>\n" % (Platform.full_name, Platform.address),
            "# $FreeBSD$\n",
        ))

    def _gen_sections(self, makefile):
        items = list(self._values.items())
        items.sort(key=lambda i: i[0])
        for _, values in groupby(items, lambda x: x[0].section):
            values = [k for j in values for k in j[0].generate(j[1])]
            tabs = max(2, int(ceil(max(len(n[0]) for n in values) + 1.0) / Platform.tab_width))
            makefile.write("\n")
            for name, value in values:
                needed_tabs = tabs - int(floor((len(name) + 1.0) / Platform.tab_width))
                makefile.write("%s=%s" % (name, "\t" * needed_tabs))
                width = tabs * Platform.tab_width
                first_line = True
                for j in value:
                    next_line = j[-1] == "\n"
                    j = j.rstrip("\n")
                    if not first_line:
                        if width == -1 or width + len(j) + 1 > Platform.page_width:
                            makefile.write(" \\\n%s" % ("\t" * tabs))
                            width = tabs * Platform.tab_width
                        else:
                            makefile.write(" ")
                            width += 1
                    first_line = False
                    makefile.write(j)
                    if next_line:
                        width = -1
                    else:
                        width += len(j)
                makefile.write("\n")

    def generate(self):
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        return makefile.getvalue()

    def get_value(self, port_value):
        # type: (PortValue) -> Union[str, List[str], PortObject]
        return self._values[port_value]

    def has_value(self, port_value):
        # type: (PortValue) -> bool
        return port_value in self._values

    def set_value(self, port_value, value):
        # type: (PortValue, Union[str, List[str], PortObject]) -> None
        self._values[port_value] = value


class CranPort(Port):
    def __init__(self, name):
        super(CranPort, self).__init__(Cran.PKGNAMEPREFIX + name)
        self.categories = ("math",)
        self.portname = name
        self.uses(Cran).add("auto-plist")


IGNORED_KEYS = [
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

INTERNAL_PACKAGES = [
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
        if name not in INTERNAL_PACKAGES:
            condition = cran.group(2).replace("-", ".").replace(" ", "") if cran.group(2) else ">0"
            depends.add(PortDependency(CranPort(name), condition))


def match_key(line):
    # type: (str) -> bool
    return bool(match("^[a-zA-Z/@]+:", line))


def make_cran_port(name):
    port = CranPort(name)
    with open("test/car/DESCRIPTION", "rU") as package:
        desc = Stream(i.rstrip('\n') for i in package.readlines())
    while desc.has_current:
        line = desc.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + i.strip() for i in desc.take_until(match_key))
        if key == "Package":
            if port.name != Cran.PKGNAMEPREFIX + value:
                msg = "CRAN: package name (%s) does not match port name (%s)" % (value, port.name)
                raise PortException(msg)
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
        elif key not in IGNORED_KEYS:
            raise PortException("CRAN: package key %s unknown at line %s" % (key, line))
    return port


car = make_cran_port("car")
print(car.generate())
