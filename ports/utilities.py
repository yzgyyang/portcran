from abc import ABCMeta, abstractproperty
from typing import Any, Callable, Iterable, Iterator, Optional

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


class Stream(Iterator[str]):  # pylint: disable=too-few-public-methods
    def __init__(self, lines: Iterable[str], filtr: Optional[Callable[[str], str]] = None, start_line: int = 0) -> None:
        if filtr is None:
            self._lines = lines if isinstance(lines, list) else list(lines)
        else:
            self._lines = [filtr(line) for line in lines]
        self._len = len(self._lines)
        self.start_line = start_line
        self.line = start_line

    def __iter__(self) -> Iterator[str]:
        return Stream(self._lines, start_line=self.start_line)

    def __next__(self) -> str:
        if 0 <= self.line < self._len:
            line = self._lines[self.line]
            self.line += 1
            return line
        raise StopIteration

    def take_while(self, condition: Callable[[str], bool], inclusive: bool = False) -> Iterable[str]:
        lines = []
        for line in self._lines[self.line:]:
            if not inclusive and not condition(line):
                break
            lines.append(line)
            if inclusive and not condition(line):
                break
        self.line += len(lines)
        return lines
