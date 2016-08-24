from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod
from ports.core.internal import Orderable
from typing import Callable, List  # pylint: disable=unused-import

__all__ = ["Dependency"]


class Dependency(Orderable):
    __metaclass__ = ABCMeta

    _factories = []  # type: List[Callable[[str, str], Dependency]]

    def __init__(self, origin):
        # type: (str) -> None
        self.origin = origin

    @abstractmethod
    def __str__(self):
        # type: () -> str
        raise NotImplementedError()

    @staticmethod
    def create(expression):
        # type: (str) -> Dependency
        target, origin = expression.split(":")
        dependency = [i for i in (j(target, origin) for j in Dependency._factories) if i is not None]
        assert len(dependency) == 1
        return dependency[0]

    @staticmethod
    def factory(factory):
        # type: (Callable[[str, str], Dependency]) -> Callable[[str, str], Dependency]
        Dependency._factories.append(factory)
        return factory

    def key(self):
        # type: () -> str
        return self.origin
