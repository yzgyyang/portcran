from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from ports.core.internal import Orderable
from typing import List, Set  # pylint: disable=unused-import

__all__ = ["Uses"]


class Uses(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        # type: (str) -> None
        self._args = set()  # type: Set[str]
        self.name = name

    def __str__(self):
        # type: () -> str
        return self.name + (":" + ",".join(sorted(self._args)) if len(self._args) else "")

    def add(self, arg):
        # type: (str) -> None
        self._args.add(arg)

    @abstractmethod
    def get_variable(self, name):
        # type: (str) -> List[str]
        raise NotImplementedError()

    def key(self):
        # type: () -> str
        return self.name
