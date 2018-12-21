"""Dependency architecture for a Port."""
from abc import ABCMeta, abstractmethod
from typing import Callable, ClassVar, List, Optional
from ports.utilities import Orderable

__all__ = ["Dependency"]


class Dependency(Orderable, metaclass=ABCMeta):
    """Base class for objects representing a dependency to a Port."""

    _factories: ClassVar[List[Callable[[str, str], Optional["Dependency"]]]] = []

    def __init__(self, origin: str) -> None:
        """Initialise the dependency with the specified port origin."""
        self.origin = origin

    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of this dependency instance."""
        raise NotImplementedError()

    @staticmethod
    def create(expression: str) -> "Dependency":
        """Create an instance of a Dependency object based on the string representation."""
        target, origin = expression.split(":")
        dependency = [i for i in (j(target, origin) for j in Dependency._factories) if i is not None]
        if not dependency:
            raise ValueError("Unknown dependency expression: %s" % expression)
        assert len(dependency) == 1
        return dependency[0]

    @staticmethod
    def factory(factory: Callable[[str, str], Optional["Dependency"]]) -> Callable[[str, str], Optional["Dependency"]]:
        """
        Decorate a function to register it as being able to create Dependency.

        The factory function will be passed the string representation and port origin.  The function must then either
        return an instance of a Dependency object, if it can parse the representation, or return None.
        """
        Dependency._factories.append(factory)
        return factory

    def key(self) -> str:
        return self.origin
