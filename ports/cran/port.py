from __future__ import absolute_import, division, print_function

from re import match
from traceback import print_exc
from plumbum.path import LocalPath  # pylint: disable=unused-import
from ports import Port, PortError, PortStub, Ports  # pylint: disable=unused-import
from ports.cran.uses import Cran
from ports.dependency import PortDependency
from ports.core.port import PortDepends  # pylint: disable=unused-import
from typing import Callable, Dict, Optional, Union  # pylint: disable=unused-import

__all__ = ["CranPort"]

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


class CranPort(Port):
    class Keywords(object):
        def __init__(self):
            # type: () -> None
            self._keywords = {}  # type: Dict[str, Callable[[CranPort, str], None]]

        def __get__(self, instance, owner):
            # type: (CranPort, type) -> Union[CranPort.Keywords, Callable[[str, str, int], None]]
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
            elif key not in IGNORED_KEYS and False:
                raise PortError("CRAN: package key %s unknown at line %s" % (key, line))

    parse = Keywords()

    def __init__(self, category, name, portdir=None):
        # type: (str, str, LocalPath) -> None
        super(CranPort, self).__init__(category, Cran.PKGNAMEPREFIX + name, portdir)
        self.distname = "${PORTNAME}_${DISTVERSION}"
        self.portname = name
        self.uses[Cran].add("auto-plist")

    @staticmethod
    def _add_dependency(depends, value, optional=False):
        # type: (PortDepends.Collection, str, bool) -> None
        for cran in (i.strip() for i in value.split(",")):
            depend = match(r"(\w+)(?:\s*\((.*)\))?", cran)
            name = depend.group(1).strip()
            if name not in INTERNAL_PACKAGES:
                try:
                    port = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + name)
                except PortError:
                    if not optional:
                        raise
                    print("Suggested package does not exist: %s" % name)
                else:
                    condition = depend.group(2).replace("-", ".").replace(" ", "") if not depend.group(2) else ">0"
                    depends.add(PortDependency(port, condition))

    @staticmethod
    @Ports.factory
    def _create(port):
        # type: (PortStub) -> Optional[CranPort]
        if port.name.startswith(Cran.PKGNAMEPREFIX):
            portname = port.name[len(Cran.PKGNAMEPREFIX):]
            port = CranPort(port.category, portname, port.portdir)
            try:
                port.load()
            except AssertionError:
                # TODO: remove once all R-cran ports have been verified
                print("Unable to load CranPort:", port.name)
                print_exc()
            assert port.portname == portname
            assert port.distname in ("${PORTNAME}_${DISTVERSION}", "${PORTNAME}_${PORTVERSION}")
            assert Cran in port.uses
            return port
        return None

    def _gen_plist(self):
        # type: () -> None
        pkg_plist = self.portdir / "pkg-plist"
        if pkg_plist.exists():
            pkg_plist.delete()

    @parse.keyword("Depends")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self._add_dependency(self.depends.run, value)

    @parse.keyword("Description")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        pass

    @parse.keyword("Imports")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self._add_dependency(self.depends.run, value)

    @parse.keyword("License")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if value == "GPL (>= 2)":
            self.license.add("GPLv2+")
        elif value == "GPL-2":
            self.license.add("GPLv2")
        else:
            raise PortError("CRAN: unknown 'License' value '%s'" % value)

    @parse.keyword("NeedsCompilation")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if value == "yes":
            self.uses[Cran].add("compiles")
            del self.no_arch
        elif value == "no":
            self.no_arch = "yes"
        else:
            raise PortError("CRAN: unknown 'NeedsCompilation' value '%s', expected 'yes' or 'no'" % value)

    @parse.keyword("Package")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if self.portname != value:
            raise PortError("CRAN: package name (%s) does not match port name (%s)" % (value, self.portname))

    @parse.keyword("Suggests")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self._add_dependency(self.depends.test, value, optional=True)

    @parse.keyword("Title")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self.comment = value

    @parse.keyword("URL")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        pass

    @parse.keyword("Version")  # type: ignore
    def parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self.distversion = value
