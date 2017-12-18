from abc import ABCMeta, abstractmethod
from io import StringIO
from itertools import groupby
from math import ceil, floor
from typing import Callable, Dict, Generic, Iterable, Iterator, List, Optional, Set, Tuple, TypeVar, Union, cast
from plumbum.cmd import make
from plumbum.path import LocalPath
from ports.core.dependency import Dependency
from ports.core.internal import MakeDict, Orderable, make_vars
from ports.core.platform import Platform
from ports.core.uses import Uses

__all__ = ["Port", "PortError", "PortStub"]


T = TypeVar("T", covariant=True)


class PortValue(Orderable, Generic[T], metaclass=ABCMeta):
    def __init__(self, section: int, order: int = 1) -> None:
        super().__init__()
        self.order = order
        self.section = section

    @abstractmethod
    def __get__(self, instance: "Port", owner: type) -> T:
        raise NotImplementedError()

    @abstractmethod
    def generate(self, value: Union[str, List[str], "PortObject"]) -> Iterable[Tuple[str, Iterable[str]]]:
        raise NotImplementedError()

    def key(self) -> Tuple[int, int]:
        return self.section, self.order

    @abstractmethod
    def load(self, obj: "Port", variables: MakeDict) -> None:
        raise NotImplementedError()


class PortVar(PortValue[Optional[str]]):
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


class PortVarList(PortValue[List[str]]):
    def __init__(self, section: int, order: int, name: str) -> None:
        super().__init__(section, order)
        self._setter: Callable[[Port, List[str]], List[str]] = lambda x, y: y
        self.name = name

    def __get__(self, instance: "Port", owner: type) -> List[str]:
        value = instance.uses.get_variable(self.name)
        if value is None:
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


class PortObject(object, metaclass=ABCMeta):
    @abstractmethod
    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        raise NotImplementedError()

    @abstractmethod
    def load(self, variables: MakeDict) -> None:
        raise NotImplementedError()


T2 = TypeVar("T2", bound=PortObject)


class PortObj(PortValue[T2]):
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


class CyclicalDependencyError(Exception):
    def __init__(self, portstub: "PortStub") -> None:
        super().__init__()
        self.cycle = [portstub]
        self._is_closed = False

    def __str__(self) -> str:
        return "Cycling dependency detected: %s" % " -> ".join(p.origin for p in self.cycle)

    def add(self, portstub: "PortStub") -> None:
        if not self._is_closed:
            self.cycle.append(portstub)
            self._is_closed = self.cycle[0] == portstub


class PortStub(object):
    def __init__(self, category: str, name: str, portdir: Optional[LocalPath] = None) -> None:
        self.category = category
        self.name = name
        self._portdir = portdir

    def __repr__(self) -> str:
        return "<Port: %s>" % self.origin

    @property
    def portdir(self) -> LocalPath:
        if self._portdir is None:
            from ports.core.ports import Ports
            return Ports.dir / self.origin
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

    uses = PortObj(5, PortUses)

    no_arch = PortVar(6, 1, "NO_ARCH")

    def __init__(self, category: str, name: str, portdir: Optional[LocalPath]) -> None:
        super().__init__(category, name, portdir)
        self._values: Dict[PortValue, Union[str, List[str], PortObject]] = {}
        self.categories = [category]
        self.changelog: Dict[str, List[str]] = {}
        self.maintainer = Platform.address
        self.portname = name

    @property
    def pkgname(self) -> str:
        return "%s%s" % (self.pkgnameprefix or "", self.portname)

    @staticmethod
    def _gen_footer(makefile: StringIO) -> None:
        makefile.write("\n.include <bsd.port.mk>\n")

    def _gen_header(self, makefile: StringIO) -> None:
        port_makefile = self.portdir / "Makefile"
        if port_makefile.exists():
            with open(port_makefile, "rU") as port_makefile:
                created_by = port_makefile.readline()
                keyword = port_makefile.readline()
        else:
            created_by = "# Created by: %s <%s>\n" % (Platform.full_name, Platform.address)
            keyword = "# $FreeBSD$\n"
        makefile.writelines((created_by, keyword))

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

    def _gen_plist(self) -> None:
        raise NotImplementedError("Generic Port does not know how to create pkg-plist")

    @categories.setter
    def categories(self, categories: List[str]) -> List[str]:
        if not categories or categories[0] != self.category:
            raise PortError("Port: invalid categories, must start with: %s" % self.category)
        return categories

    def generate(self) -> None:
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        with open(self.portdir / "Makefile", "w") as portmakefile:
            portmakefile.write(makefile.getvalue())
        make["-C", self.portdir, "makesum"]()
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

    def del_value(self, port_value: PortValue) -> None:
        if port_value in self._values:
            del self._values[port_value]

    def get_value(self, port_value: PortValue) -> Union[str, List[str], PortObject]:
        return self._values[port_value]

    def has_value(self, port_value: PortValue) -> bool:
        return port_value in self._values

    def set_value(self, port_value: PortValue, value: Union[str, List[str], PortObject]) -> None:
        self._values[port_value] = value
