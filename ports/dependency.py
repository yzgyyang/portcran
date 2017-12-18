from re import match
from typing import Optional
from ports import Dependency, Port, Ports

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
    def __init__(self, port: Port, condition: str = ">0") -> None:
        super().__init__(port.origin)
        self.port = port
        self.condition = condition

    def __str__(self) -> str:
        return "%s%s:%s" % (self.port.pkgname, self.condition, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target: str, origin: str) -> Optional["PortDependency"]:
        condition = match(r"(.*)((?:>=|>).*)", target)
        if condition is not None:
            port = Ports.get_port_by_origin(origin)
            assert condition.group(1) == port.pkgname
            return PortDependency(port, condition.group(2))
        return None
