from abc import ABCMeta, abstractproperty
from typing import Any, Callable, Iterable, Iterator

__all__ = ["Orderable", "Stream"]


class Orderable(object, metaclass=ABCMeta):
    # pylint: disable=too-few-public-methods
    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Orderable)
        return bool(self._key == other._key)  # pylint: disable=W0212

    def __hash__(self) -> int:
        return hash(self._key)

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Orderable)
        return bool(self._key < other._key)  # pylint: disable=W0212

    def __ne__(self, other: object) -> bool:
        """Determine if this object is not equal to the specified object."""
        return not self == other

    @abstractproperty
    def _key(self) -> Any:
        raise NotImplementedError()


class Stream(Iterator[str]):
    # pylint: disable=too-few-public-methods
    def __init__(self, objects: Iterable[str], filtr: Callable[[str], str] = lambda x: x, line: int = 1) -> None:
        self._objects = list(objects)
        self._filter = filtr
        self.line = line

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        if 0 <= self.line < len(self._objects):
            self.line += 1
            return self._filter(self._objects[self.line - 1])
        raise StopIteration

    def take_while(self, condition: Callable[[str], bool], inclusive: bool = False) -> Iterator[str]:
        for value in self:
            if not inclusive and not condition(value):
                self.line -= 1
                break
            yield value
            if inclusive and not condition(value):
                break
