from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from ports.core.internal import Orderable

__all__ = ["Dependency"]


class Dependency(Orderable):
    __metaclass__ = ABCMeta

    def __init__(self, origin):
        # type: (str) -> None
        self.origin = origin

    @abstractmethod
    def __str__(self):
        # type: () -> str
        raise NotImplementedError()

    def key(self):
        # type: () -> str
        return self.origin
