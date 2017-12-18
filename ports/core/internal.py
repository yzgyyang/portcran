from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from re import compile as re_compile
from typing import Any, Callable, Iterable, Iterator, List, Optional, Set, Union
from plumbum.path import LocalPath

__all__ = ["make_var", "make_vars", "Orderable", "Stream"]

VARIABLE_ASSIGNMENT = re_compile(r"^\s*(\w+)\s*([+?:]?)=(.*)$")


def make_var(portdir: LocalPath, var: str) -> List[str]:
    return make_vars(portdir)[var]


def make_vars(portdir: LocalPath) -> "MakeDict":
    variables = MakeDict()
    with open(portdir / "Makefile", "r") as makefile:
        data = Stream(makefile.readlines(), lambda x: x.split("#", 2)[0].rstrip())
        while True:
            lines = list(data.take_while(lambda x: x.endswith("\\"), inclusive=True))
            if len(lines) == 0:
                break
            var = VARIABLE_ASSIGNMENT.search(" ".join(line.rstrip("\\") for line in lines))
            if var is not None:
                name = var.group(1)
                modifier = var.group(2)
                values = var.group(3).split()
                if modifier == "+":
                    variables.extend(name, values)
                elif modifier == "?":
                    variables.add(name, values)
                else:
                    assert not modifier
                    variables.set(name, values)
    return variables


class MakeDict(object):
    def __init__(self) -> None:
        self._variables: OrderedDict[str, List[str]] = OrderedDict()
        self._internal: Set[str] = set()

    def __contains__(self, item: str) -> bool:
        return item in self._variables

    def __getitem__(self, item: str) -> List[str]:
        values = self._variables[item]
        subbed_values: List[str] = []
        for value in values:
            if value.startswith("${") and value.endswith("}"):
                variable = value[2:-1]
                if variable in self._variables:
                    subbed_values.extend(self[variable])
                    self._internal.add(variable)
                else:
                    subbed_values.append(value)
            else:
                subbed_values.append(value)
        return subbed_values

    def __str__(self) -> str:
        unpopped = []
        for key, value in list(self._variables.items()):
            if key not in self._internal:
                unpopped.append("%s=%s" % (key, value))
        return ", ".join(unpopped)

    def add(self, name: str, values: List[str]) -> None:
        if name not in self._variables:
            self.set(name, values)

    @property
    def all_popped(self) -> bool:
        return len(self._internal) == len(self._variables)

    def extend(self, name: str, values: List[str]) -> None:
        if name in self._variables:
            self._variables[name].extend(values)
        else:
            self.set(name, values)

    def pop(self, name: str, **kwargs: List[str]) -> List[str]:
        if "default" in kwargs and name not in self:
            return kwargs["default"]
        values = self[name]
        del self._variables[name]
        return values

    def pop_value(self, name: str, **kwargs: Optional[Union[str, bool]]) -> Optional[str]:
        if "default" in kwargs and name not in self:
            assert kwargs["default"] is None or isinstance(kwargs["default"], str)
            return kwargs["default"]
        values = self[name]
        del self._variables[name]
        if "combine" in kwargs and kwargs["combine"] is True:
            assert isinstance(kwargs["combine"], bool)
            value = " ".join(values)
        else:
            assert len(values) == 1
            value = values[0]
        return value

    def set(self, name: str, values: List[str]) -> None:
        self._variables[name] = values


class Orderable(object, metaclass=ABCMeta):
    # pylint: disable=too-few-public-methods
    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Orderable)
        return bool(self.key() == other.key())

    def __hash__(self) -> int:
        return hash(self.key())

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Orderable)
        return bool(self.key() < other.key())

    @abstractmethod
    def key(self) -> Any:
        raise NotImplementedError()


class Stream(Iterator[str]):
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
        else:
            raise StopIteration

    def take_while(self, condition: Callable[[str], bool], inclusive: bool = False) -> Iterator[str]:
        for value in self:
            if not inclusive and not condition(value):
                self.line -= 1
                break
            yield value
            if inclusive and not condition(value):
                break
