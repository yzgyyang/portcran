from abc import ABCMeta, abstractmethod
from typing import Callable, List, Optional  # pylint: disable=unused-import
from ports.core.internal import Orderable

__all__ = ["Dependency"]


class Dependency(Orderable, metaclass=ABCMeta):
    _factories = []  # type: List[Callable[[str, str], Optional[Dependency]]]

    def __init__(self, origin):
        # type: (str) -> None
        self.origin = origin

    def __eq__(self, other):
        # type: (Dependency) -> bool
        return self.origin == other.origin

    def __hash__(self):
        # type: () -> int
        return hash(self.origin)

    def __ne__(self, other):
        # type: (Dependency) -> bool
        return not self == other

    @abstractmethod
    def __str__(self):
        # type: () -> str
        raise NotImplementedError()

    @staticmethod
    def create(expression):
        # type: (str) -> Dependency
        target, origin = expression.split(":")
        dependency = [i for i in (j(target, origin) for j in Dependency._factories) if i is not None]
        if not dependency:
            raise ValueError("Unknown dependency expression: %s" % expression)
        assert len(dependency) == 1
        return dependency[0]

    @staticmethod
    def factory(factory):
        # type: (Callable[[str, str], Optional[Dependency]]) -> Callable[[str, str], Optional[Dependency]]
        Dependency._factories.append(factory)
        return factory

    def key(self):
        # type: () -> str
        return self.origin
