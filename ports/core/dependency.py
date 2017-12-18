from abc import ABCMeta, abstractmethod
from typing import Callable, ClassVar, List, Optional
from ports.core.internal import Orderable

__all__ = ["Dependency"]


class Dependency(Orderable, metaclass=ABCMeta):
    _factories: ClassVar[List[Callable[[str, str], Optional["Dependency"]]]] = []

    def __init__(self, origin: str) -> None:
        self.origin = origin

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Dependency) and self.origin == other.origin

    def __hash__(self) -> int:
        return hash(self.origin)

    def __ne__(self, other: object) -> bool:
        return not self == other

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError()

    @staticmethod
    def create(expression: str) -> "Dependency":
        target, origin = expression.split(":")
        dependency = [i for i in (j(target, origin) for j in Dependency._factories) if i is not None]
        if not dependency:
            raise ValueError("Unknown dependency expression: %s" % expression)
        assert len(dependency) == 1
        return dependency[0]

    @staticmethod
    def factory(factory: Callable[[str, str], Optional["Dependency"]]) -> Callable[[str, str], Optional["Dependency"]]:
        Dependency._factories.append(factory)
        return factory

    def key(self) -> str:
        return self.origin
