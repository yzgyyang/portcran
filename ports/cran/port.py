from re import compile as re_compile, match
from tarfile import TarFile
from traceback import print_exc
from typing import Callable, Dict, Optional, Union, cast
from plumbum.path import LocalPath
from ports import Port, PortError, PortStub, Ports
from ports.core.internal import Stream
from ports.cran.uses import Cran
from ports.dependency import PortDependency
from ports.core.port import PortDepends

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
    r"{day3} {month3}".format(day3=DAY3, month3=MONTH3) + \
    r"\d{2} \d{2}:\d{2}:\d{2} \w{3} \d{4})"

EMPTY_LINE = re_compile(r"^\* (?:R|man|src)/[^:]*:$")

VERSION_IDENTIFIER = [
    re_compile(r"^\* DESCRIPTION(?: \(Version\))?: (?:New version is|Version) (.+)\.$"),
    re_compile(r"^Changes to Version (.+)$"),
]

LINE = ("* ", "( ", "o ")

SECTION = [
    re_compile(r"^{date},? .* <.*>$".format(date=DATE)),
    re_compile(r"^\d{4}-\d{2}-\d{2}  .+$")
]


def extractfile(tar_file: TarFile, name: str, filtr: Callable[[str], str], line: int = 1) -> Optional[Stream]:
    try:
        stream = tar_file.extractfile(name)
    except KeyError:
        return None
    return None if stream is None else Stream((line.decode('utf-8') for line in stream.readlines()), filtr, line)


def version_identifier(line: str) -> Optional[str]:
    for regex in VERSION_IDENTIFIER:
        match = regex.match(line)
        if match:
            return match.group(1)


def section(line: str) -> bool:
    for regex in SECTION:
        match = regex.match(line)
        if match:
            return True
    return False


class CranPort(Port):
    class Keywords(object):
        def __init__(self) -> None:
            self._keywords: Dict[str, Callable[[CranPort, str], None]] = {}

        def __get__(self, instance: "CranPort", owner: type) -> Union["CranPort.Keywords", Callable[[str, str, int], None]]:
            if instance is None:
                return self
            return lambda key, value, line: self.parse(instance, key, value, line)

        def keyword(self, *keywords: str) -> Callable[[Callable[["CranPort", str], None]], "CranPort.Keywords"]:
            def assign(func: Callable[["CranPort", str], None]) -> "CranPort.Keywords":
                for keyword in keywords:
                    self._keywords[keyword] = func
                return self
            return assign

        def parse(self, port: "CranPort", key: str, value: str, line: int) -> None:
            if key in self._keywords:
                self._keywords[key](port, value)
            elif key not in IGNORED_KEYS:
                raise PortError("CRAN: package key %s unknown at line %s" % (key, line))

    _parse = Keywords()

    def __init__(self, category: str, name: str, portdir: LocalPath, distfile: Optional[TarFile] = None) -> None:
        super().__init__(category, Cran.PKGNAMEPREFIX + name, portdir)
        self.distname = "${PORTNAME}_${DISTVERSION}"
        self.portname = name
        self.uses[Cran].add("auto-plist")
        if distfile is not None:
            self._load_descr(distfile)
            self._load_changelog(distfile)

    @staticmethod
    def _add_dependency(depends: PortDepends.Collection, value: str, optional: bool = False) -> None:
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
    def _create(port: PortStub) -> Optional["CranPort"]:
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

    def _gen_plist(self) -> None:
        pkg_plist = self.portdir / "pkg-plist"
        if pkg_plist.exists():
            pkg_plist.delete()

    @_parse.keyword("Depends", "Imports")
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        self._add_dependency(self.depends.run, value)

    @_parse.keyword("Description")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        pass

    @_parse.keyword("License")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        if value == "GPL (>= 2)":
            self.license.add("GPLv2+")
        elif value == "GPL-2":
            self.license.add("GPLv2")
        else:
            raise PortError("CRAN: unknown 'License' value '%s'" % value)

    @_parse.keyword("NeedsCompilation")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        if value == "yes":
            self.uses[Cran].add("compiles")
        elif value != "no":
            raise PortError("CRAN: unknown 'NeedsCompilation' value '%s', expected 'yes' or 'no'" % value)

    @_parse.keyword("Package")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        if self.portname != value:
            raise PortError("CRAN: package name (%s) does not match port name (%s)" % (value, self.portname))

    @_parse.keyword("Suggests")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        self._add_dependency(self.depends.test, value, optional=True)

    @_parse.keyword("Title")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        self.comment = value

    @_parse.keyword("URL")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        pass

    @_parse.keyword("Version")  # type: ignore
    def _parse(self, value: str) -> None:
        # pylint: disable=function-redefined
        self.distversion = value

    def _load_changelog(self, distfile: TarFile) -> None:
        for name in ("ChangeLog", "NEWS"):
            changelog = extractfile(distfile, "%s/%s" % (self.portname, name), lambda x: x.strip(), line=0)
            if changelog is not None:
                break
        else:
            return
        version = self.distversion
        assert version is not None
        prev_line = ""
        while True:
            for line in changelog.take_while(lambda l: not version_identifier(l)):
                if line == "" or section(line):
                    prev_line = ""
                    continue
                if line is not None:
                    if version not in self.changelog:
                        self.changelog[version] = []
                    if line[:2] in LINE:
                        if EMPTY_LINE.match(line) is None:
                            prev_line = ""
                            self.changelog[version].append(line[2:])
                        else:
                            prev_line = line[2:]
                    elif not self.changelog[version]:
                        self.changelog[version].append(prev_line + line)
                    else:
                        self.changelog[version][-1] += prev_line + " " + line
                        prev_line = ""
            try:
                version = version_identifier(next(changelog))
                prev_line = ""
            except StopIteration:
                break

    def _load_descr(self, distfile: TarFile) -> None:
        desc = extractfile(distfile, "%s/DESCRIPTION" % self.portname, lambda x: x.rstrip('\n'))
        if desc is None:
            raise NameError("CRAN '%s' package missing DESCRIPTION file")
        identifier = re_compile(r"^[a-zA-Z/@]+:")
        for line in desc:
            key, value = line.split(":", 1)
            value = value.strip() + "".join(" " + i.strip() for i in desc.take_while(lambda l: not identifier.match(l)))
            self._parse(key, value, desc.line)  # type: ignore

    @staticmethod
    def create(name: str, distfile: LocalPath, portdir: Optional[str] = None) -> "CranPort":
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
        cran = CranPort(categories[0], name, portdir, TarFile.open(str(distfile), "r:gz"))
        cran.maintainer = maintainer
        cran.categories = categories
        return cran
