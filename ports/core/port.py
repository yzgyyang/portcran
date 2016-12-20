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
from typing import Any, Callable, Dict, Iterable, Iterator, List, Set, Tuple, Union  # pylint: disable=unused-import

__all__ = ["Port", "PortError", "PortStub"]


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

    @abstractmethod
    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        raise NotImplementedError()


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
            value = instance.uses.get_variable(self.name)
            if value is None:
                value = [None]
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
            self.__set__(obj, " ".join(variables.pop(self.name)))


class PortVarList(PortValue):
    def __init__(self, section, order, name):
        # type: (int, int, str) -> None
        super(PortVarList, self).__init__(section, order)
        self._setter = lambda x, y: y
        self.name = name

    def __get__(self, instance, owner):
        # type: (Port, type) -> List[str]
        value = instance.get_value(self) if instance.has_value(self) else None
        if isinstance(value, list):
            value = instance.uses.get_variable(self.name, value)
        else:
            assert value is None
            value = instance.uses.get_variable(self.name)
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
            obj.set_value(self, variables.pop(self.name))

    def setter(self, setter):
        # type: (Callable[[Port, List[str]], List[str]]) -> PortVarList
        self._setter = setter
        return self


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

    def load(self, obj, variables):
        # type: (Port, MakeDict) -> None
        self.__get__(obj, Port).load(variables)


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


class PortLicense(PortObject):
    def __init__(self):
        # type: () -> None
        super(PortLicense, self).__init__()
        self._licenses = set()  # type: Set[str]
        self.combination = None  # type: str
        self.file = None  # type: str

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
            if "LICENSE_COMB" in variables:
                license_comb = variables.pop("LICENSE_COMB")
                assert len(license_comb) == 1
                self.combination = license_comb[0]
            if "LICENSE_FILE" in variables:
                license_file = variables.pop("LICENSE_FILE")
                assert len(license_file) == 1
                self.file = license_file[0]


class PortDepends(PortObject):
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
            if name in variables:
                for depend in variables.pop(name):
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

    def get_variable(self, name, value=None):
        # type: (str, List[str]) -> List[str]
        values = [v for v in (u.get_variable(name) for u in self._uses.values()) if v is not None]
        if len(values) > 1:
            raise PortError("PortUses: multiple uses define value for variable '%s'" % name)
        return values[0] if len(values) else value

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        yield ("USES", (str(u) for u in sorted(self._uses.values())))
        for uses in sorted(self._uses.values()):
            # TODO: convert to yield return for Python 3.3+
            for tuple in uses.generate():
                yield tuple

    def load(self, variables):
        # type: (MakeDict) -> None
        if "USES" in variables:
            for use in variables.pop("USES"):
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


class PortStub(object):  # pylint: disable=too-few-public-methods
    def __init__(self, category, name, portdir=None):
        # type: (str, str, LocalPath) -> None
        from ports.core.ports import Ports
        self.category = category  # type: str
        self.name = name  # type: str
        self.portdir = Ports.dir / self.origin if portdir is None else portdir  # type: LocalPath

    def __repr__(self):
        # type: () -> str
        return "<Port: %s>" % self.origin

    @property
    def origin(self):
        # type: () -> str
        return "%s/%s" % (self.category, self.name)


class Port(PortStub):
    portname = PortVar(1, 1, "PORTNAME")  # type: str
    portversion = PortVar(1, 2, "PORTVERSION")  # type: str
    distversion = PortVar(1, 4, "DISTVERSION")  # type: str
    portrevision = PortVar(1, 6, "PORTREVISION")  # type: str
    categories = PortVarList(1, 8, "CATEGORIES")  # type: List[str]
    pkgnameprefix = PortVar(1, 12, "PKGNAMEPREFIX")  # type: str
    distname = PortVar(1, 14, "DISTNAME")  # type: str

    maintainer = PortVar(2, 1, "MAINTAINER")  # type: str
    comment = PortVar(2, 2, "COMMENT")  # type: str

    license = PortObj(3, PortLicense)  # type: PortLicense

    depends = PortObj(4, PortDepends)  # type: PortDepends

    uses = PortObj(5, PortUses)  # type: PortUses

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

    @categories.setter  # type: ignore
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

    def get_value(self, port_value):
        # type: (PortValue) -> Union[str, List[str], PortObject]
        return self._values[port_value]

    def has_value(self, port_value):
        # type: (PortValue) -> bool
        return port_value in self._values

    def set_value(self, port_value, value):
        # type: (PortValue, Union[str, List[str], PortObject]) -> None
        self._values[port_value] = value
