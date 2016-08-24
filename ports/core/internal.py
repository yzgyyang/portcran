from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from re import compile as re_compile
from plumbum.path import LocalPath  # pylint: disable=unused-import
from typing import Any, Callable, Dict, Iterable, List  # pylint: disable=unused-import

__all__ = ["make_var", "make_vars", "Orderable", "Stream"]

VARIABLE_ASSIGNMENT = re_compile(r"^\s*(\w+)\s*([+?:]?)=(.*)$")


def make_var(portdir, var):
    # type: (LocalPath, str) -> List[str]
    return make_vars(portdir)[var]


def make_vars(portdir):
    # type: (LocalPath) -> Dict[str, List[str]]
    variables = OrderedDict()  # type: Dict[str, List[str]]
    with open(portdir / "Makefile", "r") as makefile:
        data = Stream(makefile.readlines(), lambda x: x.split("#", 2)[0].rstrip())
        while data.has_current:
            line = " ".join(i.rstrip("\\") for i in data.take_while(lambda x: x.endswith("\\"), inclusive=True))
            var = VARIABLE_ASSIGNMENT.search(line)
            if var:
                name = var.group(1)
                modifier = var.group(2)
                values = var.group(3).split()
                if modifier == "+" and name in variables:
                    variables[name].extend(values)
                elif modifier != "?":
                    variables[name] = values
    return variables


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
    def __init__(self, objects, filtr=lambda x: x):
        # type: (Iterable[str], Callable[[str], str]) -> None
        self._objects = list(objects)
        self._filter = filtr
        self.line = 1

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

    def take_until(self, condition):
        # type: (Callable[[str], bool]) -> Iterable[str]
        while self.next():
            value = self.current
            if not condition(value):
                yield value
            else:
                break
