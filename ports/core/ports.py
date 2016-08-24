from __future__ import absolute_import, division, print_function

from os import environ
from plumbum.path import LocalPath
from ports.core.internal import make_var
from ports.core.port import Port, PortError, PortStub  # pylint: disable=unused-import
from typing import Callable  # pylint: disable=unused-import

__all__ = ["Ports"]


class Ports(object):
    _factories = []  # type: List[Callable[[PortStub], Port]]
    _ports = []  # type: List[PortStub]
    dir = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make_var(dir, "SUBDIR")
    distdir = LocalPath(make_var(dir, "DISTDIR")[0])

    @staticmethod
    def _load_ports():
        # type: () -> None
        for category in Ports.categories:
            for name in make_var(Ports.dir / category, "SUBDIR"):
                name = str(name)  # NOTE: remove in Python 3
                Ports._ports.append(PortStub(category, name, Ports.dir / category / name))

    @staticmethod
    def get_port_by_name(name):
        # type: (str) -> Port
        if not len(Ports._ports):
            Ports._load_ports()
        ports = [i for i in Ports._ports if i.name == name]
        if not len(ports):
            raise PortError("Ports: no port with name '%s' in collection" % name)
        if len(ports) > 1:
            raise PortError("Ports: multiple ports with name '%s' in collection" % name)
        for factory in reversed(Ports._factories):
            port = factory(ports[0])
            if port is not None:
                return port
        raise PortError("Ports: unable to create port from origin '%s'" % ports[0].origin)

    @staticmethod
    def factory(factory):
        # type: (Callable[[PortStub], Port]) -> Callable[[PortStub], Port]
        Ports._factories.append(factory)
        return factory
