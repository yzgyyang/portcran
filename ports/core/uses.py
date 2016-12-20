from __future__ import absolute_import, division, print_function

from abc import ABCMeta
from ports.core.internal import MakeDict, Orderable  # pylint: disable=unused-import
from typing import Callable, Dict, Iterable, List, Set, Tuple  # pylint: disable=unused-import

__all__ = ["Uses"]


class Uses(Orderable):
    __metaclass__ = ABCMeta

    _uses = {}  # type: Dict[str, type]

    def __init__(self, name):
        # type: (str) -> None
        self._args = set()  # type: Set[str]
        self.name = name

    def __contains__(self, item):
        # type: (str) -> bool
        return item in self._args

    def __iter__(self):
        # type: () -> Iterable[str]
        return iter(self._args)

    def __str__(self):
        # type: () -> str
        return self.name + (":" + ",".join(sorted(self._args)) if len(self._args) else "")

    @staticmethod
    def get(name):
        # type: (str) -> type
        return Uses._uses[name]

    @staticmethod
    def register(name):
        # type: (str) -> Callable[[type], type]
        def doregister(klass):
            # type: (type) -> type
            assert issubclass(klass, Uses)
            Uses._uses[name] = klass
            return klass
        return doregister

    def add(self, arg):
        # type: (str) -> None
        self._args.add(arg)

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        # pylint: disable=no-self-use
        return iter(())

    def get_variable(self, name):
        # type: (str) -> List[str]
        pass

    def key(self):
        # type: () -> str
        return self.name

    def load(self, variables):
        # type: (MakeDict) -> None
        pass
