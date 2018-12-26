from re import compile as re_compile
from typing import Optional
from .core import Dependency

__all__ = ['BinDependency', 'LibDependency', 'LocalBaseDependency', 'PortDependency']


class BinDependency(Dependency):
    pattern = re_compile(r'([0-9a-zA-Z_.-]+)')

    def __init__(self, binname: str, origin: str) -> None:
        super().__init__(origin)
        self.binname = binname

    def __str__(self) -> str:
        return '%s:%s' % (self.binname, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional[Dependency]:
        condition = BinDependency.pattern.fullmatch(target)
        if condition is not None:
            return BinDependency(condition.group(1), origin)
        return None


class LibDependency(Dependency):
    pattern = re_compile(r'lib(.*).so')

    def __init__(self, libname: str, origin: str) -> None:
        super().__init__(origin)
        self.libname = libname

    def __str__(self) -> str:
        return 'lib%s.so:%s' % (self.libname, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional['LibDependency']:
        condition = LibDependency.pattern.fullmatch(target)
        if condition is not None:
            return LibDependency(condition.group(1), origin)
        return None


class LocalBaseDependency(Dependency):
    pattern = re_compile(r'\${LOCALBASE}/(.*)')

    def __init__(self, path: str, origin: str) -> None:
        super().__init__(origin)
        self.path = path

    def __str__(self) -> str:
        return '${LOCALBASE}/%s:%s' % (self.path, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional[Dependency]:
        condition = LocalBaseDependency.pattern.fullmatch(target)
        if condition is not None:
            return LocalBaseDependency(condition.group(1), origin)
        return None


class PortDependency(Dependency):
    pattern = re_compile(r'(.*)((?:>=|>).*)')

    def __init__(self, pkgname: str, condition: str, origin: str) -> None:
        super().__init__(origin)
        self.pkgname = pkgname
        self.condition = condition

    def __str__(self) -> str:
        return '%s%s:%s' % (self.pkgname, self.condition, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional[Dependency]:
        condition = PortDependency.pattern.match(target)
        if condition is not None:
            return PortDependency(condition.group(1), condition.group(2), origin)
        return None
