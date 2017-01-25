from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from re import compile as re_compile
from types import NoneType
from plumbum.path import LocalPath  # pylint: disable=unused-import
from typing import Any, Callable, Dict, Iterable, List, Set, Union  # pylint: disable=unused-import

__all__ = ["make_var", "make_vars", "Orderable", "Stream"]

VARIABLE_ASSIGNMENT = re_compile(r"^\s*(\w+)\s*([+?:]?)=(.*)$")


def make_var(portdir, var):
    # type: (LocalPath, str) -> List[str]
    return make_vars(portdir)[var]


def make_vars(portdir):
    # type: (LocalPath) -> MakeDict
    variables = MakeDict()
    with open(portdir / "Makefile", "r") as makefile:
        data = Stream(makefile.readlines(), lambda x: x.split("#", 2)[0].rstrip())
        while data.has_current:
            line = " ".join(i.rstrip("\\") for i in data.take_while(lambda x: x.endswith("\\"), inclusive=True))
            var = VARIABLE_ASSIGNMENT.search(line)
            if var:
                name = var.group(1)
                modifier = var.group(2)
                values = var.group(3).split()
                if modifier == "+":
                    variables.extend(name, values)
                elif modifier == "?":
                    variables.add(name, values)
                else:
                    assert not len(modifier)
                    variables.set(name, values)

    return variables


class MakeDict(object):
    def __init__(self):
        # type: () -> None
        self._variables = OrderedDict()  # type: OrderedDict[str, List[str]]
        self._internal = set()  # type: Set[str]

    def __contains__(self, item):
        # type: (str) -> bool
        return item in self._variables

    def __getitem__(self, item):
        # type: (str) -> List[str]
        values = self._variables[item]
        subbed_values = []  # type: List[str]
        for value in values:
            if value.startswith("${") and value.endswith("}"):
                variable = value[2:-1]
                if variable in self._variables:
                    subbed_values.extend(self[variable])
                    self._internal.add(variable)
                else:
                    subbed_values.append(value)
            else:
                subbed_values.append(value)
        return subbed_values

    def __str__(self):
        # type: () -> str
        unpopped = []
        for key, value in self._variables.items():
            if key not in self._internal:
                unpopped.append("%s=%s" % (key, value))
        return ", ".join(unpopped)

    def add(self, name, values):
        # type: (str, List[str]) -> None
        if name not in self._variables:
            self.set(name, values)

    @property
    def all_popped(self):
        # type: () -> bool
        return len(self._internal) == len(self._variables)

    def extend(self, name, values):
        # type: (str, List[str]) -> None
        if name in self._variables:
            self._variables[name].extend(values)
        else:
            self.set(name, values)

    def pop(self, name, **kwargs):
        # type: (str, **List[str]) -> List[str]
        if "default" in kwargs and name not in self:
            return kwargs["default"]
        values = self[name]
        del self._variables[name]
        return values

    def pop_value(self, name, **kwargs):
        # type: (str, **Union[str, bool]) -> str
        if "default" in kwargs and name not in self:
            assert isinstance(kwargs["default"], (str, NoneType))
            return kwargs["default"]
        values = self[name]
        del self._variables[name]
        if "combine" in kwargs and kwargs["combine"]:
            assert isinstance(kwargs["combine"], bool)
            value = " ".join(values)
        else:
            assert len(values) == 1
            value = values[0]
        return value

    def set(self, name, values):
        # type: (str, List[str]) -> None
        self._variables[name] = values


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


class Stream(object):
    def __init__(self, objects, filtr=lambda x: x, line=1):
        # type: (Iterable[str], Callable[[str], str]) -> None
        self._objects = list(objects)
        self._filter = filtr
        self.line = line

    @property
    def current(self):
        # type: () -> str
        return self._filter(self._objects[self.line - 1])

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

    def take_while(self, condition, inclusive=False):
        # type: (Callable[[str], bool], bool) -> Iterable[str]
        while self.has_current:
            value = self.current
            if not inclusive and not condition(value):
                break
            yield value
            self.next()
            if inclusive and not condition(value):
                break
