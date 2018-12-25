"""Classes describing a FreeBSD Port and the various structures."""
from abc import ABCMeta, abstractmethod
from io import StringIO
from itertools import groupby
from math import ceil, floor
from pathlib import Path
from typing import (Any, Callable, Dict, Generic, IO, Iterable, Iterator, List, Optional, Set, Tuple, TypeVar, Union,
                    cast)
from .dependency import Dependency
from .make import MakeDict, make_vars
from .platform import Platform
from .ports import MAKE
from .uses import Uses
from ..utilities import Orderable

__all__ = ["Port", "PortError", "PortStub"]


T = TypeVar("T", covariant=True)  # pylint: disable=C0103


def peek(file: IO[Any], length: int) -> str:
    pos = file.tell()
    value = file.read(length)
    file.seek(pos)
    return value


class PortValue(Orderable, Generic[T], metaclass=ABCMeta):  # pylint: disable=E1136
    def __init__(self, section: int, order: int = 1) -> None:
        super().__init__()
        self.order = order
        self.section = section

    @abstractmethod
    def __get__(self, instance: "Port", owner: type) -> T:
        raise NotImplementedError()

    @property
    def _key(self) -> Tuple[int, int]:
        return self.section, self.order

    @abstractmethod
    def generate(self, value: Union[str, List[str], "PortObject"]) -> Iterable[Tuple[str, Iterable[str]]]:
        raise NotImplementedError()

    @abstractmethod
    def load(self, obj: "Port", variables: MakeDict) -> None:
        raise NotImplementedError()


class PortVar(PortValue[Optional[str]]):  # pylint: disable=E1136
    def __init__(self, section: int, order: int, name: str) -> None:
        super().__init__(section, order)
        self.name = name

    def __delete__(self, instance: "Port") -> None:
        instance.del_value(self)

    def __get__(self, instance: "Port", owner: type) -> Optional[str]:
        value = instance.uses.get_variable(self.name)
        if value is None:
            if instance.has_value(self):
                return cast(str, instance.get_value(self))
            return None
        else:
            assert len(value) == 1 and isinstance(value[0], str)
            return value[0]

    def __set__(self, obj: "Port", value: str) -> None:
        obj.set_value(self, value)

    def generate(self, value: Union[str, List[str], "PortObject"]) -> Iterable[Tuple[str, Iterable[str]]]:
        assert isinstance(value, str)
        return (self.name, (value,)),

    def load(self, obj: "Port", variables: MakeDict) -> None:
        if self.name in variables:
            value = variables.pop_value(self.name, combine=True)
            assert value is not None
            self.__set__(obj, value)


class PortVarList(PortValue[List[str]]):  # pylint: disable=E1136
    def __init__(self, section: int, order: int, name: str) -> None:
        super().__init__(section, order)
        self._setter: Callable[[Port, List[str]], List[str]] = lambda x, y: y
        self.name = name

    def __get__(self, instance: "Port", owner: type) -> List[str]:
        value = instance.uses.get_variable(self.name)
        if value is None:
            if not instance.has_value(self):
                self.__set__(instance, [])
            value = cast(List[str], instance.get_value(self))
        assert isinstance(value, list)
        return value

    def __set__(self, obj: "Port", value: List[str]) -> None:
        obj.set_value(self, self._setter(obj, value))

    def generate(self, value: Union[str, List[str], "PortObject"]) -> Iterable[Tuple[str, Iterable[str]]]:
        assert isinstance(value, list)
        return (self.name, value),

    def load(self, obj: "Port", variables: MakeDict) -> None:
        if self.name in variables:
            self.__set__(obj, variables.pop(self.name))

    def setter(self, setter: Callable[["Port", List[str]], List[str]]) -> "PortVarList":
        self._setter = setter
        return self


class PortObject(object, metaclass=ABCMeta):  # pylint: disable=E1136
    @abstractmethod
    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        raise NotImplementedError()

    @abstractmethod
    def load(self, variables: MakeDict) -> None:
        raise NotImplementedError()


T2 = TypeVar("T2", bound=PortObject)


class PortObj(PortValue[T2]):  # pylint: disable=E1136
    def __init__(self, section: int, factory: Callable[[], T2]) -> None:
        super().__init__(section)
        self.factory = factory

    def __get__(self, instance: "Port", owner: type) -> T2:
        if not instance.has_value(self):
            instance.set_value(self, self.factory())
        return cast(T2, instance.get_value(self))

    def generate(self, value: Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]:
        # pylint: disable=no-self-use
        return cast(T2, value).generate()

    def load(self, obj: "Port", variables: MakeDict) -> None:
        self.__get__(obj, Port).load(variables)


class PortLicense(PortObject, Iterable[str]):
    def __init__(self) -> None:
        super().__init__()
        self._licenses: Set[str] = set()
        self.combination: Optional[str] = None
        self.file: Optional[str] = None

    def __iter__(self) -> Iterator[str]:
        return iter(self._licenses)

    def add(self, license_type: str) -> "PortLicense":
        self._licenses.add(license_type)
        return self

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        yield ("LICENSE", sorted(self._licenses))
        if self.combination is not None:
            yield ("LICENSE_COMB", (self.combination,))
        if self.file is not None:
            yield ("LICENSE_FILE", (self.file,))

    def load(self, variables: MakeDict) -> None:
        if "LICENSE" in variables:
            for license_type in variables.pop("LICENSE"):
                self.add(license_type)
            self.combination = variables.pop_value("LICENSE_COMB", default=None)
            self.file = variables.pop_value("LICENSE_FILE", default=None)


class PortDepends(PortObject):
    # pylint: disable=too-few-public-methods
    class Collection(object):
        def __init__(self, name: str) -> None:
            self.name = name
            self._depends: List[Dependency] = []

        def __iter__(self) -> Iterator[Dependency]:
            return iter(self._depends)

        def add(self, dependency: Dependency) -> None:
            if dependency not in self._depends:
                self._depends.append(dependency)
            else:
                raise KeyError("%s: dependency '%s' already registered" % (self.name, dependency))

    def __init__(self) -> None:
        super().__init__()
        self._depends: List[PortDepends.Collection] = []
        self.build = self._make_depends("BUILD_DEPENDS")
        self.lib = self._make_depends("LIB_DEPENDS")
        self.run = self._make_depends("RUN_DEPENDS")
        self.test = self._make_depends("TEST_DEPENDS")

    def _make_depends(self, name: str,) -> "PortDepends.Collection":
        depends = PortDepends.Collection(name)
        self._depends.append(depends)
        return depends

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        return ((i.name, (str(d) + "\n" for d in sorted(i))) for i in self._depends if any(i))

    def load(self, variables: MakeDict) -> None:
        for depends in self._depends:
            for depend in variables.pop(depends.name, default=[]):
                depends.add(Dependency.create(depend))


class PortBroken(PortObject):
    class Category(object):
        def __init__(self, arch: str = None, opsys: str = None, osrel: str = None) -> None:
            self.arch = arch
            self.opsys = opsys
            self.osrel = osrel

        def __eq__(self, other: object) -> bool:
            if isinstance(other, PortBroken.Category):
                return self.arch == other.arch and self.opsys == other.opsys and self.osrel == other.osrel
            return False

        def __hash__(self) -> int:
            return hash(str(self))

        def __str__(self) -> str:
            subcat: List[str] = []
            if self.opsys is not None:
                subcat.append(self.opsys)
                if self.osrel is not None:
                    subcat.append(self.osrel)
                    if self.arch is not None:
                        subcat.append(self.arch)
            elif self.arch is not None:
                subcat.append(self.arch)
            if subcat:
                return "BROKEN_" + "_".join(subcat)
            else:
                return "BROKEN"

        @staticmethod
        def create(makevar: str) -> "PortBroken.Category":
            subcat = makevar.split("_")[1:]
            arch = None
            opsys = None
            osrel = None
            if len(subcat) > 1:
                opsys = subcat[0]
                osrel = subcat[1]
                if len(subcat) == 3:
                    arch = subcat[2]
            elif len(subcat) == 1:
                if subcat[0] == "FreeBSD":
                    opsys = subcat[0]
                else:
                    arch = subcat[0]
            return PortBroken.Category(arch, opsys, osrel)

    def __init__(self) -> None:
        super().__init__()
        self.reasons: Dict[PortBroken.Category, str] = {}

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        broken: Dict[str, str] = {}
        for category, reason in self.reasons.items():
            broken[str(category)] = reason
        for category_name in sorted(broken.keys()):
            yield (category_name, (broken[category_name],))

    def load(self, variables: MakeDict) -> None:
        for variable in variables.variables:
            if variable.startswith("BROKEN"):
                self.reasons[PortBroken.Category.create(variable)] = " ".join(variables.pop(variable))


class PortUses(PortObject):
    def __init__(self) -> None:
        super().__init__()
        self._uses: Dict[type, Uses] = {}

    def __contains__(self, item: Union[type, str]) -> bool:
        if isinstance(item, str):
            item = Uses.get(item)
        return item in self._uses

    def __getitem__(self, item: Union[type, str]) -> Uses:
        if isinstance(item, str):
            item = Uses.get(item)
        if item not in self._uses:
            self._uses[item] = item()
        return self._uses[item]

    def get_variable(self, name: str) -> Optional[List[str]]:
        values = [v for v in (u.get_variable(name) for u in list(self._uses.values())) if v is not None]
        if len(values) > 1:
            raise PortError("PortUses: multiple uses define value for variable '%s'" % name)
        return values[0] if values else None

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        yield ("USES", (str(u) for u in sorted(self._uses.values())))
        for uses in sorted(self._uses.values()):
            yield from uses.generate()

    def load(self, variables: MakeDict) -> None:
        for use in variables.pop("USES", default=[]):
            uses_var = use.split(":")
            assert 1 <= len(uses_var) <= 2
            name = uses_var[0]
            args = uses_var[1].split(",") if len(uses_var) == 2 else []
            uses = self[name]
            for arg in args:
                uses.add(arg)
            uses.load(variables)


class PortError(Exception):
    pass


class PortStub(object):
    def __init__(self, category: str, name: str, portdir: Optional[Path] = None) -> None:
        self.category = category
        self.name = name
        self._portdir = portdir

    def __repr__(self) -> str:
        return "<Port: %s>" % self.origin

    @property
    def portdir(self) -> Path:
        if self._portdir is None:
            from ports.core.ports import Ports
            return Ports.dir / self.category / self.name
        return self._portdir

    @property
    def origin(self) -> str:
        return "%s/%s" % (self.category, self.name)


class Port(PortStub):
    portname = PortVar(1, 1, "PORTNAME")
    portversion = PortVar(1, 2, "PORTVERSION")
    distversion = PortVar(1, 4, "DISTVERSION")
    portrevision = PortVar(1, 6, "PORTREVISION")
    categories = PortVarList(1, 8, "CATEGORIES")
    pkgnameprefix = PortVar(1, 12, "PKGNAMEPREFIX")
    distname = PortVar(1, 14, "DISTNAME")

    maintainer = PortVar(2, 1, "MAINTAINER")
    comment = PortVar(2, 2, "COMMENT")

    license = PortObj(3, PortLicense)

    depends = PortObj(4, PortDepends)

    broken = PortObj(5, PortBroken)

    uses = PortObj(6, PortUses)

    no_arch = PortVar(7, 1, "NO_ARCH")

    def __init__(self, category: str, name: str, portdir: Optional[Path]) -> None:
        self._values: Dict[PortValue, Union[str, List[str], PortObject]] = {}
        self.categories = [category]
        super().__init__(category, name, portdir)
        self.changelog: Dict[str, List[str]] = {}
        self.maintainer = Platform.address
        self.portname = name
        self.description: Optional[str] = None
        self.website: Optional[str] = None

    @property  # type: ignore
    def category(self) -> str:  # type: ignore
        return self.categories[0]

    @category.setter
    def category(self, value: str) -> None:  # type: ignore
        categories = self.categories
        if value in categories:
            categories.remove(value)
        self.categories = [value] + categories

    @categories.setter
    def categories(self, categories: List[str]) -> List[str]:
        if not categories:
            raise PortError("Port: invalid categories, must start with: %s" % self.category)
        return categories

    @property
    def descr(self) -> Path:
        return self.portdir / "pkg-descr"

    @property
    def pkgname(self) -> str:
        return "%s%s" % (self.pkgnameprefix or "", self.portname)

    @property
    def version(self) -> str:
        if self.distversion is not None:
            return self.distversion
        assert self.portversion is not None
        return self.portversion

    @staticmethod
    def _gen_footer(makefile: StringIO) -> None:
        makefile.write("\n.include <bsd.port.mk>\n")

    def _gen_header(self, makefile: StringIO) -> None:
        port_makefile = self.portdir / "Makefile"
        metadata: List[str] = []
        if port_makefile.exists():
            with port_makefile.open("rU") as makefile_file:
                for line in iter(makefile_file.readline, ""):
                    if line.startswith("# Created by") or line.startswith("# $FreeBSD"):
                        metadata.append(line)
                    if peek(makefile_file, 1) != "#":
                        break
        else:
            metadata.append("# $FreeBSD$\n")
        makefile.writelines(metadata)

    def _gen_sections(self, makefile: StringIO) -> None:
        for _, items in groupby(sorted(list(self._values.items()), key=lambda k: k[0]), lambda k: k[0].section):
            values = [j for i in items for j in i[0].generate(i[1])]
            if not values:
                continue
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

    def _gen_distinfo(self) -> None:
        MAKE("-C", self.portdir, "makesum")

    def _gen_descr(self) -> None:
        if self.description is None:
            if self.descr.exists():
                self.descr.unlink()
        else:
            with self.descr.open("w") as descr:
                width = 0
                for word in self.description.split():
                    next_line = word[-1] == "\n"
                    word = word.rstrip("\n")
                    if width == -1 or width + len(word) + 1 > 79:
                        descr.write("\n")
                        width = 0
                    elif width:
                        descr.write(" ")
                        width += 1
                    descr.write(word)
                    if next_line:
                        width = -1
                    else:
                        width += len(word)
                descr.write("\n")
                if self.website is not None:
                    descr.write("\nWWW: %s\n" % self.website)

    def _gen_plist(self) -> None:
        raise NotImplementedError("Generic Port does not know how to create pkg-plist")

    def generate(self) -> None:
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        with open(self.portdir / "Makefile", "w") as portmakefile:
            portmakefile.write(makefile.getvalue())
        self._gen_distinfo()
        self._gen_descr()
        self._gen_plist()

    def load(self) -> None:
        variables = make_vars(self.portdir)
        bases = [type(self)]
        i = 0
        while i < len(bases):
            bases.extend(j for j in bases[i].__bases__ if j not in bases)
            for var in list(vars(bases[i]).values()):
                if isinstance(var, PortValue):
                    var.load(self, variables)
            i += 1
        if not variables.all_popped:
            # TODO: remove once all R-cran ports have been verified
            print("Unloaded variables for %s:" % self.name, variables)
        assert variables.all_popped
        if self.descr.exists():
            with self.descr.open() as descr:
                lines = descr.readlines()
                if lines[-1].startswith("WWW"):
                    self.website = lines[-1].split()[1]
                    lines.pop()
                    if lines[-1] == "\n":
                        lines.pop()
                self.description = " ".join(l.strip() for l in lines)

    def del_value(self, port_value: PortValue) -> None:
        if port_value in self._values:
            del self._values[port_value]

    def get_value(self, port_value: PortValue) -> Union[str, List[str], PortObject]:
        return self._values[port_value]

    def has_value(self, port_value: PortValue) -> bool:
        return port_value in self._values

    def set_value(self, port_value: PortValue, value: Union[str, List[str], PortObject]) -> None:
        self._values[port_value] = value
