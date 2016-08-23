from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from typing import Any  # pylint: disable=unused-import

__all__ = ["Orderable"]


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
