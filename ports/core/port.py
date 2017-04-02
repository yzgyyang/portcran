from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from itertools import groupby
from math import ceil, floor
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO  # type: ignore
from plumbum.cmd import make
from plumbum.path import LocalPath  # pylint: disable=unused-import
from ports.core.dependency import Dependency  # pylint: disable=unused-import
from ports.core.internal import MakeDict, Orderable, make_vars  # pylint: disable=unused-import
from ports.core.platform import Platform
from ports.core.uses import Uses  # pylint: disable=unused-import
from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Set, Tuple, TypeVar, Union, cast  # pylint: disable=unused-import

__all__ = ["Port", "PortError", "PortStub"]


T = TypeVar("T", covariant=True)


class PortValue(Orderable, Generic[T]):
    __metaclass__ = ABCMeta

    def __init__(self, section, order=1):
        # type: (int, int) -> None
        self.order = order
        self.section = section

    @abstractmethod
    def __get__(self, instance, owner):
        # type: (Port, type) -> T
        raise NotImplementedError()

    @abstractmethod
    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        raise NotImplementedError()

    def key(self):
        # type: () -> Tuple[int, int]
        return self.section, self.order

    @abstractmethod
    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        raise NotImplementedError()


class PortVar(PortValue[str]):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVar, self).__init__(section, order)
        self.name = name

    def __delete__(self, instance):
        # type: (Port) -> None
        instance.del_value(self)

    def __get__(self, instance, owner):
        # type: (Port, type) -> str
        value = instance.uses.get_variable(self.name)  # type: Optional[List[str]]
        if value is None:
            value = cast(List[str], instance.get_value(self))
        assert len(value) == 1
        return value[0]

    def __set__(self, obj, value):
        # type: (Port, str) -> None
        obj.set_value(self, value)

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        assert isinstance(value, str)
        return (self.name, (value,)),

    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        if self.name in variables:
            value = variables.pop_value(self.name, combine=True)
            assert value is not None
            self.__set__(obj, value)


class PortVarList(PortValue[List[str]]):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVarList, self).__init__(section, order)
        self._setter = lambda x, y: y  # type: Callable[[Port, List[str]], List[str]]
        self.name = name

    def __get__(self, instance, owner):
        # type: (Port, type) -> List[str]
        value = instance.uses.get_variable(self.name)  # type: Optional[List[str]]
        if value is None:
            value = cast(List[str], instance.get_value(self))
        return value

    def __set__(self, obj, value):
        # type: (Port, List[str]) -> None
        obj.set_value(self, self._setter(obj, value))

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        assert isinstance(value, list)
        return (self.name, value),

    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        if self.name in variables:
            self.__set__(obj, variables.pop(self.name))

    def setter(self, setter):
        # type: (Callable[[Port, List[str]], List[str]]) -> PortVarList
        self._setter = setter
        return self


class PortObject(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        raise NotImplementedError()

    @abstractmethod
    def load(self, variables):
        # type: (MakeDict) -> None
        raise NotImplementedError()


TPortObject = TypeVar("TPortObject", bound=PortObject)


class PortObj(PortValue[TPortObject]):
    def __init__(self, section, factory):
        # type: (int, Callable[[], TPortObject]) -> None
        super(PortObj, self).__init__(section)
        self.factory = factory

    def __get__(self, instance, owner):
        # type: (Port, type) -> TPortObject
        if not instance.has_value(self):
            instance.set_value(self, self.factory())
        return cast(TPortObject, instance.get_value(self))

    def generate(self, value):
        # type: (Union[str, List[str], PortObject]) -> Iterable[Tuple[str, Iterable[str]]]
        return cast(TPortObject, value).generate()

    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        self.__get__(obj, Port).load(variables)


class PortLicense(PortObject, Iterable[str]):
    def __init__(self):
        # type: () -> None
        super(PortLicense, self).__init__()
        self._licenses = set()  # type: Set[str]
        self.combination = None  # type: Optional[str]
        self.file = None  # type: Optional[str]

    def __iter__(self):
        # type: () -> Iterator[str]
        return iter(self._licenses)

    def add(self, license_type):
        # type: (str) -> PortLicense
        self._licenses.add(license_type)
        return self

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        yield ("LICENSE", sorted(self._licenses))
        if self.combination is not None:
            yield ("LICENSE_COMB", (self.combination,))
        if self.file is not None:
            yield ("LICENSE_FILE", (self.file,))

    def load(self, variables):
        # type: (MakeDict) -> None
        if "LICENSE" in variables:
            for license_type in variables.pop("LICENSE"):
                self.add(license_type)
            self.combination = variables.pop_value("LICENSE_COMB", default=None)
            self.file = variables.pop_value("LICENSE_FILE", default=None)


class PortDepends(PortObject, Iterable[Tuple[str, Set[Dependency]]]):
    # pylint: disable=too-few-public-methods
    class Collection(object):
        def __init__(self, depends):
            # type: (Set[Dependency]) -> None
            self._depends = depends

        def __iter__(self):
            # type: () -> Iterable[Dependency]
            return iter(self._depends)

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
        self.build = self._make_depends("BUILD_DEPENDS")
        self.lib = self._make_depends("LIB_DEPENDS")
        self.run = self._make_depends("RUN_DEPENDS")
        self.test = self._make_depends("TEST_DEPENDS")

    def __iter__(self):
        # type: () -> Iterator[Tuple[str, Set[Dependency]]]
        return iter(self._depends.items())

    def _make_depends(self, name):
        # type: (str) -> PortDepends.Collection
        depends = set()  # type: Set[Dependency]
        self._depends[name] = depends
        return PortDepends.Collection(depends)

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        return ((k, (str(d) + "\n" for d in sorted(v))) for k, v in self._depends.items() if len(v))

    def load(self, variables):
        # type: (MakeDict) -> None
        for name, depends in self:
            for depend in variables.pop(name, default=[]):
                depends.add(Dependency.create(depend))


class PortUses(PortObject):
    def __init__(self):
        # type: () -> None
        super(PortUses, self).__init__()
        self._uses = {}  # type: Dict[type, Uses]

    def __contains__(self, item):
        # type: (Union[type, str]) -> bool
        if isinstance(item, str):
            item = Uses.get(item)
        return item in self._uses

    def __getitem__(self, item):
        # type: (Union[type, str]) -> Uses
        if isinstance(item, str):
            item = Uses.get(item)
        if item not in self._uses:
            self._uses[item] = item()
        return self._uses[item]

    def get_variable(self, name):
        # type: (str) -> Optional[List[str]]
        values = [v for v in (u.get_variable(name) for u in self._uses.values()) if v is not None]
        if len(values) > 1:
            raise PortError("PortUses: multiple uses define value for variable '%s'" % name)
        return values[0] if len(values) > 0 else None

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        yield ("USES", (str(u) for u in sorted(self._uses.values())))
        for uses in sorted(self._uses.values()):
            # TODO: convert to yield return for Python 3.3+
            for variable in uses.generate():
                yield variable

    def load(self, variables):
        # type: (MakeDict) -> None
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
    def __init__(self, category, name, portdir=None):
        # type: (str, str, LocalPath) -> None
        self.category = category  # type: str
        self.name = name  # type: str
        self._portdir = portdir

    def __repr__(self):
        # type: () -> str
        return "<Port: %s>" % self.origin

    @property
    def portdir(self):
        # type: () -> LocalPath
        from ports.core.ports import Ports
        return self._portdir if self._portdir else Ports.dir / self.origin

    @property
    def origin(self):
        # type: () -> str
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

    def __init__(self, category, name, portdir):
        # type: (str, str, LocalPath) -> None
        super(Port, self).__init__(category, name, portdir)
        self._values = {}  # type: Dict[PortValue, Union[str, List[str], PortObject]]
        self.categories = [category]
        self.maintainer = Platform.address
        self.portname = name

    @property
    def pkgname(self):
        # type: () -> str
        return "%s%s" % (self.pkgnameprefix or "", self.portname)

    @staticmethod
    def _gen_footer(makefile):
        # type: (StringIO) -> None
        makefile.write("\n.include <bsd.port.mk>\n")

    def _gen_header(self, makefile):
        # type: (StringIO) -> None
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
        # type: (StringIO) -> None
        for _, items in groupby(sorted(self._values.items(), key=lambda k: k[0]), lambda k: k[0].section):
            values = [j for i in items for j in i[0].generate(i[1])]
            if not len(values):
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

    def _gen_plist(self):
        # type: () -> None
        raise NotImplementedError("Generic Port does not know how to create pkg-plist")

    @categories.setter
    def categories(self, categories):
        # type: (List[str]) -> List[str]
        if not len(categories) or categories[0] != self.category:
            raise PortError("Port: invalid categories, must start with: %s" % self.category)
        return categories

    def generate(self):
        # type: () -> None
        makefile = StringIO()
        self._gen_header(makefile)
        self._gen_sections(makefile)
        self._gen_footer(makefile)
        with open(self.portdir / "Makefile", "w") as portmakefile:
            portmakefile.write(makefile.getvalue())
        make["-C", self.portdir, "makesum"]()
        self._gen_plist()

    def load(self):
        # type: () -> None
        variables = make_vars(self.portdir)
        bases = [type(self)]  # type: List[type]
        i = 0
        while i < len(bases):
            bases.extend(j for j in bases[i].__bases__ if j not in bases)
            for var in vars(bases[i]).values():
                if isinstance(var, PortValue):
                    var.load(self, variables)
            i += 1
        if not variables.all_popped:
            # TODO: remove once all R-cran ports have been verified
            print("Unloaded variables for %s:" % self.name, variables)
        assert variables.all_popped

    def del_value(self, port_value):
        # type: (PortValue) -> None
        if port_value in self._values:
            del self._values[port_value]

    def get_value(self, port_value):
        # type: (PortValue) -> Union[str, List[str], PortObject]
        return self._values[port_value]

    def has_value(self, port_value):
        # type: (PortValue) -> bool
        return port_value in self._values

    def set_value(self, port_value, value):
        # type: (PortValue, Union[str, List[str], PortObject]) -> None
        self._values[port_value] = value
