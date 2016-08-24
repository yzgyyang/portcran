from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from plumbum.cmd import make
from plumbum.path import LocalPath  # pylint: disable=unused-import
from typing import Any  # pylint: disable=unused-import

__all__ = ["Orderable"]


def make_var(portdir, var, makefile="Makefile"):
    # type: (LocalPath, str, str) -> List[str]
    return make_vars2(portdir, makefile, var)[var]


def make_vars(portdir, *args):
    # type: (LocalPath, *str) -> Dict[str, List[str]]
    return make_vars2(portdir, "Makefile", *args)


def make_vars2(portdir, makefile, *args):
    # type: (LocalPath, str, *str) -> Dict[str, List[str]]
    vars2 = {}
    for var, line in zip(args, make[["-C", portdir, "-f" + makefile] + ["-V" + i for i in args]].split("\n")):
        vars2[var] = [str(i) for i in line.split()]
    return vars2


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
