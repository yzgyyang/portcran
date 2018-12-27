"""Simple representation of a bmake(1) Makefile."""
from collections import OrderedDict
from pathlib import Path
from os import environ
from re import compile as re_compile
from subprocess import check_output
from typing import Dict, Iterable, List, Optional, Set
from ..utilities import Stream

__all__ = ["MakeDict", "make_var", "make_vars"]

MAKE_CMD = environ.get("MAKE", default="make")

VARIABLE_ASSIGNMENT = re_compile(r"^\s*(\w+)\s*([+?:]?)=\s*(.*)$")


def make(path: Path, *args: str) -> str:
    return check_output((MAKE_CMD, '-C', str(path)) + args, text=True)


def make_var(path: Path, var: str) -> List[str]:
    """Return a specified variable from the Makefile in the specified path."""
    return make_vars(path)[var]


def make_vars(path: Path) -> "MakeDict":
    """Return an object representing the variables from the Makefile in the specified path."""
    variables = MakeDict()
    with open(path / "Makefile", "r") as makefile:
        data = Stream(makefile.readlines(), lambda x: x.split("#", 2)[0].rstrip())
        while True:
            lines = data.take_while(lambda x: x.endswith("\\"), inclusive=True)
            if not lines:
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
                elif modifier == ":":
                    variables.add(name, values)
                    variables.set(name, variables[name])
                else:
                    assert not modifier
                    variables.set(name, values)
    return variables


class MakeDict:
    """
    A representation of a bmake(1) Makefile.

    This class only handles a simplified subset of the bmake(1) Makefile.  Only variable assingment and simple
    variable expansion is supported.

    The following Makefile variable assignment operators map to this class as follows:
     - "=" -> MakeDict.set()
     - "+=" -> MakeDict.extend()
     - "?=" -> MakeDict.add()
     - ":=" -> not directly supported (but MakeDict.set(MakeDict[n])) could approximate)
    """

    def __init__(self) -> None:
        """Initialise a new instance of the MakeDict class."""
        self._variables: Dict[str, List[str]] = OrderedDict()
        self._internal: Set[str] = set()

    def __contains__(self, item: str) -> bool:
        """Indicate if the specified variable name is contained in this collection."""
        return item in self._variables

    def __getitem__(self, item: str) -> List[str]:
        """Get a variable's value, expanding if needed."""
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
        """Return a string representation of all public variables."""
        unpopped = []
        for key, value in self._variables.items():
            if key not in self._internal:
                unpopped.append("%s=%s" % (key, value))
        return ", ".join(unpopped)

    def add(self, name: str, values: List[str]) -> None:
        """Add (if not existing) the specified variable name and list of string values to this collection."""
        if name not in self._variables:
            self.set(name, values)

    @property
    def all_popped(self) -> bool:
        """Indicate if all variables have been popped."""
        return len(self._internal) == len(self._variables)

    @property
    def variables(self) -> Iterable[str]:
        """List of public variable names in this collection."""
        return [var for var in self._variables.keys() if var not in self._internal]

    def extend(self, name: str, values: List[str]) -> None:
        """Extend the specified variable with the specified list of strings."""
        if name in self._variables:
            self._variables[name].extend(values)
        else:
            self.set(name, values)

    def pop(self, name: str, **kwargs: List[str]) -> List[str]:
        """
        Pop the specified variable from this collection as a list of strings.

        If the keyword "default" is passed then that value, a list of strings, is returns if the specified variable
        does not exist in this collection.
        """
        if "default" in kwargs and name not in self:
            return kwargs["default"]
        values = self[name]
        del self._variables[name]
        if name in self._internal:
            self._internal.remove(name)
        return values

    def pop_value(self, name: str, combine=False, **kwargs: Optional[str]) -> Optional[str]:
        """
        Pop the specified variable from this collection as a single string.

        If the keyword "default" is passed then that value, a string, is returns if the specified variable does not
        exist in this collection.

        By default the variable is expected to contain a single value.  However, if "combine" is set to a value of
        `True` then values are combined into a single string using a single space as the combining seperator.
        """
        if "default" in kwargs and name not in self:
            return kwargs["default"]
        values = self.pop(name)
        if combine:
            value = " ".join(values)
        else:
            assert len(values) == 1
            value = values[0]
        return value

    def set(self, name: str, values: List[str]) -> None:
        """Set the specified variable to the specified value."""
        self._variables[name] = values
