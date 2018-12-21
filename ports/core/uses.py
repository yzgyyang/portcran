from abc import ABCMeta
from typing import Callable, ClassVar, Dict, Iterable, List, Optional, Set, Tuple
from ports.core.make import MakeDict
from ports.utilities import Orderable

__all__ = ["Uses"]


class Uses(Orderable, metaclass=ABCMeta):
    _uses: ClassVar[Dict[str, type]] = {}

    def __init__(self, name: str) -> None:
        self._args: Set[str] = set()
        self.name = name

    def __contains__(self, item: str) -> bool:
        return item in self._args

    def __iter__(self) -> Iterable[str]:
        return iter(self._args)

    def __str__(self) -> str:
        return self.name + (":" + ",".join(sorted(self._args)) if self._args else "")

    @property
    def _key(self) -> str:
        return self.name

    @staticmethod
    def get(name: str) -> type:
        return Uses._uses[name]

    @staticmethod
    def register(name: str) -> Callable[[type], type]:
        def doregister(klass: type) -> type:
            assert issubclass(klass, Uses)
            Uses._uses[name] = klass
            return klass
        return doregister

    def add(self, arg: str) -> None:
        self._args.add(arg)

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        # pylint: disable=no-self-use
        return iter(())

    def get_variable(self, name: str) -> Optional[List[str]]:
        pass

    def load(self, variables: MakeDict) -> None:
        pass
