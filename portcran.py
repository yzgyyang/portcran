#!/usr/bin/env python3
from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser
from collections import OrderedDict
from itertools import groupby
from math import ceil, floor
from os import getuid, environ
from pwd import getpwuid
from re import match, search
from socket import gethostname
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO  # type: ignore
from sys import argv
from tarfile import open as taropen
from urllib import urlretrieve
from urllib2 import urlopen
from plumbum.cmd import make
from plumbum.path import LocalPath
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Union  # pylint: disable=unused-import


class Orderable(object):
    # pylint: disable=too-few-public-methods
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
        # type: () -> Any
        raise NotImplementedError()


class Platform(object):
    # pylint: disable=too-few-public-methods
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
    def __get__(self, instance, owner):
        # type: (Port, type) -> Any
        raise NotImplementedError()

    @abstractmethod
    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        raise NotImplementedError()

    def key(self):
        # type: () -> Tuple[int, int]
        return self.section, self.order


class PortVar(PortValue):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVar, self).__init__(section, order)
        self.name = name

    def __get__(self, instance, owner):
        # type: (Port, type) -> str
        value = instance.get_value(self) if instance.has_value(self) else None
        if isinstance(value, str):
            value = instance.uses.get_variable(self.name, [value])
        else:
            assert value is None
            value = instance.uses.get_variable(self.name, None)
        return value[0]

    def __set__(self, obj, value):
        # type: (Port, str) -> None
        obj.set_value(self, value)

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        assert isinstance(value, str)
        return (self.name, (value,)),


class PortVarList(PortValue):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVarList, self).__init__(section, order)
        self.name = name

    def __get__(self, instance, owner):
        # type: (Port, type) -> List[str]
        value = instance.get_value(self) if instance.has_value(self) else None
        if isinstance(value, list):
            value = instance.uses.get_variable(self.name, value)
        else:
            assert value is None
            value = instance.uses.get_variable(self.name, None)
        return value

    def __set__(self, obj, value):
        # type: (Port, List[str]) -> None
        obj.set_value(self, value)

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        assert isinstance(value, list)
        return (self.name, value),


class PortObj(PortValue):
    def __init__(self, section, factory):
        # type: (int, Callable[[], PortObject]) -> None
        super(PortObj, self).__init__(section)
        self.factory = factory

    def __get__(self, instance, owner):
        # type: (Port, type) -> PortObject
        if not instance.has_value(self):
            instance.set_value(self, self.factory())
        value = instance.get_value(self)
        assert isinstance(value, PortObject)
        return value

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        assert isinstance(value, PortObject)
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
        self.combination = None  # type: str

    def add(self, license_type):
        # type: (str) -> PortLicense
        self._licenses.add(license_type)
        return self

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        yield ("LICENSE", sorted(self._licenses))
        if self.combination is not None:
            yield ("LICENSE_COMB", (self.combination,))


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
    # pylint: disable=too-few-public-methods
    class Collection(object):
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
        # type: (str) -> PortDepends.Collection
        depends = set()  # type: Set[Dependency]
        self._depends[name] = depends
        return PortDepends.Collection(depends)

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        return ((k, (str(d) + "\n" for d in sorted(v))) for k, v in self._depends.items() if len(v))


class Uses(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        # type: (str) -> None
        self._args = set()  # type: Set[str]
        self.name = name

    def __str__(self):
        # type: () -> str
        return self.name + (":" + ",".join(sorted(self._args)) if len(self._args) else "")

    def add(self, arg):
        # type: (str) -> None
        self._args.add(arg)

    @abstractmethod
    def get_variable(self, name):
        # type: (str) -> List[str]
        raise NotImplementedError()

    def key(self):
        # type: () -> str
        return self.name


class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self):
        # type: () -> None
        super(Cran, self).__init__("cran")

    def get_variable(self, name):
        # type: (str) -> List[str]
        if name == "PKGNAMEPREFIX":
            return [Cran.PKGNAMEPREFIX]
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
        # type: (str, List[str]) -> List[str]
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
    portname = PortVar(1, 1, "PORTNAME")  # type: str
    distversion = PortVar(1, 4, "DISTVERSION")  # type: str
    categories = PortVarList(1, 8, "CATEGORIES")  # type: List[str]
    pkgnameprefix = PortVar(1, 12, "PKGNAMEPREFIX")  # type: str
    distname = PortVar(1, 14, "DISTNAME")  # type: str

    maintainer = PortVar(2, 1, "MAINTAINER")  # type: str
    comment = PortVar(2, 2, "COMMENT")  # type: str

    license = PortObj(3, PortLicense)  # type: PortLicense

    depends = PortObj(4, PortDepends)  # type: PortDepends

    uses = PortObj(5, PortUses)  # type: PortUses

    def __init__(self, category, name, portdir=None):
        # type: (str, str, LocalPath) -> None
        self._values = {}  # type: Dict[PortValue, Union[str, List[str], PortObject]]
        self._portdir = portdir
        self.categories = [category]
        self.maintainer = Platform.address
        self.name = name
        self.portname = name

    def __repr__(self):
        return "<Port: %s>" % self.origin

    @property
    def origin(self):
        # type: () -> str
        return "%s/%s" % (self.categories[0], self.pkgname)

    @property
    def portdir(self):
        # type: () -> LocalPath
        return Ports.dir / self.origin if self._portdir is None else self._portdir

    @portdir.setter
    def portdir(self, portdir):
        # type: (LocalPath) -> None
        self._portdir = portdir

    @property
    def pkgname(self):
        # type: () -> str
        return "%s%s" % (self.pkgnameprefix, self.portname)

    @staticmethod
    def _gen_footer(makefile):
        # type: (file) -> None
        makefile.write("\n.include <bsd.port.mk>\n")

    def _gen_header(self, makefile):
        # type: (file) -> None
        port_makefile = self.portdir / "Makefile"
        if port_makefile.exists():
            with open(port_makefile, "rU") as port_makefile:
                created_by = port_makefile.readline()
                keyword = port_makefile.readline()
        else:
            created_by = "# Created by: %s <%s>\n" % (Platform.full_name, Platform.address)
            keyword = "# $FreeBSD$\n"
        makefile.writelines((created_by, keyword))

    def _gen_sections(self, makefile):
        # type: (file) -> None
        for _, items in groupby(sorted(self._values.items(), key=lambda k: k[0]), lambda k: k[0].section):
            values = [j for i in items for j in i[0].generate(i[1])]
            tabs = max(2, int(ceil(max(len(n[0]) for n in values) + 1.0) / Platform.tab_width))
            makefile.write("\n")
            for name, value in values:
                needed_tabs = tabs - int(floor((len(name) + 1.0) / Platform.tab_width))
                makefile.write("%s=%s" % (name, "\t" * needed_tabs))
                width = tabs * Platform.tab_width
                first_line = True
                for i in value:
                    next_line = i[-1] == "\n"
                    i = i.rstrip("\n")
                    if not first_line:
                        if width == -1 or width + len(i) + 1 > Platform.page_width:
                            makefile.write(" \\\n%s" % ("\t" * tabs))
                            width = tabs * Platform.tab_width
                        else:
                            makefile.write(" ")
                            width += 1
                    first_line = False
                    makefile.write(i)
                    if next_line:
                        width = -1
                    else:
                        width += len(i)
                makefile.write("\n")

    def generate(self):
        # type: () -> None
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        with open(self.portdir / "Makefile", "w") as portmakefile:
            portmakefile.write(makefile.getvalue())

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
    class Keywords(object):
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

        def __init__(self):
            # type: () -> None
            self._keywords = {}  # type: Dict[str, Callable[[CranPort, str], None]]

        def __get__(self, instance, owner):
            if instance is None:
                return self
            return lambda key, value, line: self.parse(instance, key, value, line)

        def keyword(self, keyword):
            # type: (str) -> Callable[[Callable[[CranPort, str], None]], CranPort.Keywords]
            def assign(func):
                # type: (Callable[[CranPort, str], None]) -> CranPort.Keywords
                self._keywords[keyword] = func
                return self
            return assign

        def parse(self, port, key, value, line):
            # type: (CranPort, str, str, int) -> None
            if key in self._keywords:
                self._keywords[key](port, value)
            elif key not in self.IGNORED_KEYS and False:
                raise PortException("CRAN: package key %s unknown at line %s" % (key, line))

    parse = Keywords()

    def __init__(self, category, name, portdir=None):
        # type: (str, str, LocalPath) -> None
        super(CranPort, self).__init__(category, Cran.PKGNAMEPREFIX + name, portdir)
        self.distname = "${PORTNAME}_${DISTVERSION}"
        self.portname = name
        self.uses(Cran).add("auto-plist")

    @parse.keyword("Depends")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        pass

    @parse.keyword("Description")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        pass

    @parse.keyword("Imports")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        add_dependency(self.depends.run, value)

    @parse.keyword("License")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        if value == "GPL (>= 2)":
            self.license.add("GPLv2").add("GPLv3").combination = "dual"
        else:
            raise PortException("CRAN: unknown 'License' value '%s'" % value)

    @parse.keyword("NeedsCompilation")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        if value == "yes":
            self.uses(Cran).add("compiles")  # type: ignore
        elif value != "no":
            raise PortException("CRAN: unknown 'NeedsCompilation' value '%s', expected 'yes' or 'no'" % value)

    @parse.keyword("Package")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        if self.portname != value:
            raise PortException("CRAN: package name (%s) does not match port name (%s)" % (value, self.portname))

    @parse.keyword("Suggests")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        add_dependency(self.depends.test, value, optional=True)

    @parse.keyword("Title")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        self.comment = value + " for R"

    @parse.keyword("URL")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        pass

    @parse.keyword("Version")  # type: ignore
    def parse(self, value):  # pylint: disable=function-redefined
        # type: (str) -> None
        self.distversion = value


INTERNAL_PACKAGES = [
    "KernSmooth",
    "MASS",
    "Matrix",
    "R",
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


def add_dependency(depends, value, optional=False):
    # type: (PortDepends.Collection, str, bool) -> None
    for cran in (i.strip() for i in value.split(",")):
        depend = match(r"(\w+)(?:\s*\((.*)\))?", cran)
        name = depend.group(1).strip()
        if name not in INTERNAL_PACKAGES:
            condition = depend.group(2).replace("-", ".").replace(" ", "") if depend.group(2) else ">0"
            port = get_cran_port(name)
            if port is None:
                if not optional:
                    raise PortException("CRAN: package '%s' not in Ports" % name)
            else:
                depends.add(PortDependency(port, condition))


def match_key(line):
    # type: (str) -> bool
    return bool(match("^[a-zA-Z/@]+:", line))


def make_cran_port(name, portdir=None):
    # type: (str, LocalPath) -> CranPort
    print("Cheching for latest version...")
    site_page = urlopen("http://cran.r-project.org/package=%s" % name).read()
    version = search(r"<td>Version:</td>\s*<td>(.*?)</td>", site_page).group(1)
    distfile = Ports.distdir / ("%s_%s.tar.gz" % (name, version))
    if not distfile.exists():  # pylint: disable=no-member
        print("Fetching package source...")
        urlretrieve("https://cran.r-project.org/src/contrib/%s" % distfile.name, distfile)  # pylint: disable=no-member
    if portdir.exists():
        categories = make["-C", portdir, "-VCATEGORIES"]().split()
    else:
        categories = ["math"]
    cran = CranPort(categories[0], name, portdir)
    if len(categories) > 1:
        cran.categories = categories
    with taropen(str(distfile), "r:gz") as distfile:
        desc = Stream(i.rstrip('\n') for i in distfile.extractfile("%s/DESCRIPTION" % name).readlines())
    while desc.has_current:
        line = desc.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + i.strip() for i in desc.take_until(match_key))
        cran.parse(key, value, desc.line)  # type: ignore
    return cran


class Ports(object):
    # pylint: disable=too-few-public-methods
    dir = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make["-C", dir, "-VSUBDIR"]().split()
    distdir = LocalPath(make["-C", dir / "Mk", "-fbsd.port.mk", "-VDISTDIR"]().strip())


CRAN_PORTS = {}  # type: Dict[str, CranPort]


def get_cran_port(name):
    # type (str) -> CranPort
    if not len(CRAN_PORTS):
        for portdir in Ports.dir.walk(
                filter=lambda i: i.name.startswith(Cran.PKGNAMEPREFIX),
                dir_filter=lambda i: str(i)[len(str(Ports.dir)) + 1:].find('/') == -1 and i.name in Ports.categories):
            cran_name = portdir.name[len(Cran.PKGNAMEPREFIX):]
            port = CranPort([portdir.split()[-2]], cran_name, portdir)
            CRAN_PORTS[cran_name] = port
    if name in CRAN_PORTS:
        return CRAN_PORTS[name]


def update():
    parser = ArgumentParser()
    parser.add_argument("name", help="Name of the CRAN package")
    parser.add_argument("-o", "--output", help="Output directory")

    parser.add_argument("-a", "--address", help="Creator/maintainer's e-mail address")

    args = parser.parse_args()

    if args.address is not None:
        Platform.address = args.address

    portdir = None if args.output is None else LocalPath(args.output)
    cran = make_cran_port(args.name, portdir)
    cran.generate()


def main():
    if len(argv) == 1:
        print("usage: portcran update [-o OUTPUT] name")
        exit(2)
    action = argv.pop(1)
    if action == "update":
        update()

if __name__ == "__main__":
    main()
