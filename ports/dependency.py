from __future__ import absolute_import, division, print_function

from ports import Dependency, PortStub  # pylint: disable=unused-import

__all__ = ["PortDependency"]


class PortDependency(Dependency):
    def __init__(self, port, condition=">0"):
        # type: (PortStub, str) -> None
        super(PortDependency, self).__init__(port.origin)
        self.port = port
        self.condition = condition

    def __str__(self):
        # type: () -> str
        return "%s%s:%s" % (self.port.pkgname, self.condition, self.origin)
