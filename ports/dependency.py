from __future__ import absolute_import, division, print_function

from re import match
from ports import Dependency, Port, Ports  # pylint: disable=unused-import
from typing import Optional  # pylint: disable=unused-import

__all__ = ["LibDependency", "PortDependency"]


class LibDependency(Dependency):
    def __init__(self, libname, origin):
        # type: (str, str) -> None
        super(LibDependency, self).__init__(origin)
        self.libname = libname

    def __str__(self):
        # type: () -> str
        return "lib%s.so:%s" % (self.libname, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target, origin):
        # type: (str, str) -> Optional[LibDependency]
        condition = match("lib(.*).so", target)
        if condition is not None:
            return LibDependency(condition.group(1), origin)
        return None


class PortDependency(Dependency):
    def __init__(self, port, condition=">0"):
        # type: (Port, str) -> None
        super(PortDependency, self).__init__(port.origin)
        self.port = port
        self.condition = condition

    def __str__(self):
        # type: () -> str
        return "%s%s:%s" % (self.port.pkgname, self.condition, self.origin)

    @staticmethod
    @Dependency.factory
    def _create(target, origin):
        # type: (str, str) -> Optional[PortDependency]
        condition = match("(.*)((?:>=|>).*)", target)
        if condition is not None:
            port = Ports.get_port_by_origin(origin)
            assert condition.group(1) == port.pkgname
            return PortDependency(port, condition.group(2))
        return None
