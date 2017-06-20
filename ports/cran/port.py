from __future__ import absolute_import, division, print_function

from re import compile as recompile, match
from tarfile import TarFile
from traceback import print_exc
from typing import Callable, Dict, Optional, Union, cast  # pylint: disable=unused-import
from plumbum.path import LocalPath  # pylint: disable=unused-import
from ports import Port, PortError, PortStub, Ports  # pylint: disable=unused-import
from ports.core.internal import Stream
from ports.cran.uses import Cran
from ports.dependency import PortDependency
from ports.core.port import PortDepends  # pylint: disable=unused-import

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

EMPTY_LOG = [
    "",
    "* R/*.R:",
    "* src/*c:",
]

DAY3 = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"

MONTH3 = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"

DATE = r"(?:\d{4}-\d{2}-\d{2}|" + \
    r"{day3} {month3} \d{two} \d{two}:\d{two}:\d{two} \w{three} \d{four})".format(day3=DAY3, month3=MONTH3,
                                                                                  two="{2}", three="{3}", four="{4}")


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

        def keyword(self, *keywords):
            # type: (*str) -> Callable[[Callable[[CranPort, str], None]], CranPort.Keywords]
            def assign(func):
                # type: (Callable[[CranPort, str], None]) -> CranPort.Keywords
                for keyword in keywords:
                    self._keywords[keyword] = func
                return self
            return assign

        def parse(self, port, key, value, line):
            # type: (CranPort, str, str, int) -> None
            if key in self._keywords:
                self._keywords[key](port, value)
            elif key not in IGNORED_KEYS:
                raise PortError("CRAN: package key %s unknown at line %s" % (key, line))

    _parse = Keywords()

    def __init__(self, category, name, portdir):
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
                    condition = ">0" if not depend.group(2) else depend.group(2).replace("-", ".").replace(" ", "")
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

    @_parse.keyword("Depends", "Imports")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self._add_dependency(self.depends.run, value)

    @_parse.keyword("Description")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        pass

    @_parse.keyword("License")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if value == "GPL (>= 2)":
            self.license.add("GPLv2+")
        elif value == "GPL-2":
            self.license.add("GPLv2")
        else:
            raise PortError("CRAN: unknown 'License' value '%s'" % value)

    @_parse.keyword("NeedsCompilation")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if value == "yes":
            self.uses[Cran].add("compiles")
            del self.no_arch
        elif value == "no":
            self.no_arch = "yes"
        else:
            raise PortError("CRAN: unknown 'NeedsCompilation' value '%s', expected 'yes' or 'no'" % value)

    @_parse.keyword("Package")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        if self.portname != value:
            raise PortError("CRAN: package name (%s) does not match port name (%s)" % (value, self.portname))

    @_parse.keyword("Suggests")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self._add_dependency(self.depends.test, value, optional=True)

    @_parse.keyword("Title")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self.comment = value

    @_parse.keyword("URL")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        pass

    @_parse.keyword("Version")  # type: ignore
    def _parse(self, value):
        # type: (str) -> None # pylint: disable=function-redefined
        self.distversion = value

    def _load_changelog(self, distfile):
        # type: (TarFile) -> None
        try:
            changelog = distfile.extractfile("%s/ChangeLog" % self.portname).readlines()
            changelog = Stream(changelog, lambda x: x.strip(), line=0)
        except NameError:
            return
        version = self.distversion
        assert version is not None
        empty_line = recompile(r"^\* (?:R|man|src)/[^:]*:$")
        version_identifier = recompile(r"^\* DESCRIPTION(?: \(Version\))?: (?:New version is|Version) (.*)\.$")
        section = recompile(r"^{date},? .* <.*>$".format(date=DATE))
        prev_line = ""
        while changelog.next():
            for line in changelog.take_while(lambda l: not version_identifier.match(l)):
                if line == "" or section.match(line) is not None:
                    prev_line = ""
                    continue
                if line is not None:
                    if version not in self.changelog:
                        self.changelog[version] = []
                    if line[:2] in ("* ", "( "):
                        if empty_line.match(line) is None:
                            prev_line = ""
                            self.changelog[version].append(line[2:])
                        else:
                            prev_line = line[2:]
                    elif not self.changelog[version]:
                        self.changelog[version].append(prev_line + line)
                    else:
                        self.changelog[version][-1] += prev_line + " " + line
                        prev_line = ""
            if changelog.has_current:
                version = version_identifier.search(changelog.current).group(1)
                prev_line = ""
                assert version not in self.changelog

    def _load_descr(self, distfile):
        # type: (TarFile) -> None
        desc = Stream(i.rstrip('\n') for i in distfile.extractfile("%s/DESCRIPTION" % self.portname).readlines())
        identifier = recompile(r"^[a-zA-Z/@]+:")
        while desc.has_current:
            key, value = desc.current.split(":", 1)
            desc.next()
            value = value.strip() + "".join(" " + i.strip() for i in desc.take_while(lambda l: not identifier.match(l)))
            self._parse(key, value, desc.line)  # type: ignore

    @staticmethod
    def create(name, distfile, portdir=None):
        # type: (str, LocalPath, Optional[str]) -> CranPort
        categories = ["math"]
        maintainer = "ports@FreeBSD.org"
        try:
            port = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + name)
            categories = port.categories
            maintainer = cast(str, port.maintainer)
        except PortError:
            pass
        if portdir is not None:
            portdir = LocalPath(portdir)
        cran = CranPort(categories[0], name, portdir)
        cran.maintainer = maintainer
        cran.categories = categories
        with TarFile.open(str(distfile), "r:gz") as distfile:
            cran._load_descr(distfile)
            cran._load_changelog(distfile)
        return cran
