from re import match
from typing import Optional
from .core import Dependency

__all__ = ["LibDependency", "LocalBaseDependency", "PortDependency"]


class LibDependency(Dependency):
    def __init__(self, libname: str, origin: str) -> None:
        super().__init__(origin)
        self.libname = libname

    def __str__(self) -> str:
        return "lib%s.so:%s" % (self.libname, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional["LibDependency"]:
        condition = match(r"lib(.*).so", target)
        if condition is not None:
            return LibDependency(condition.group(1), origin)
        return None


class LocalBaseDependency(Dependency):
    def __init__(self, path: str, origin: str) -> None:
        super().__init__(origin)
        self.path = path

    def __str__(self) -> str:
        return "${LOCALBASE}/%s:%s" % (self.path, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional["LocalBaseDependency"]:
        condition = match(r"\${LOCALBASE}/(.*)", target)
        if condition is not None:
            return LocalBaseDependency(condition.group(1), origin)
        return None


class PortDependency(Dependency):
    def __init__(self, pkgname: str, condition: str, origin: str) -> None:
        super().__init__(origin)
        self.pkgname = pkgname
        self.condition = condition

    def __str__(self) -> str:
        return "%s%s:%s" % (self.pkgname, self.condition, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional["PortDependency"]:
        condition = match(r"(.*)((?:>=|>).*)", target)
        if condition is not None:
            return PortDependency(condition.group(1), condition.group(2), origin)
        return None
