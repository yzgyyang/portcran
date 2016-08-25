from __future__ import absolute_import, division, print_function

from os import environ
from plumbum.cmd import make
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
    distdir = LocalPath(make["-C", dir / "Mk", "-VDISTDIR", "-fbsd.port.mk"]().strip())

    @staticmethod
    def _get_port(selector):
        # type: (Callable[[PortStub], bool]) -> Port
        if not len(Ports._ports):
            Ports._load_ports()
        ports = [i for i in Ports._ports if selector(i)]
        if not len(ports):
            raise PortError("Ports: no port matches requirement")
        if len(ports) > 1:
            raise PortError("Ports: multiple ports match requirement")
        if type(ports[0]) is PortStub:  # pylint: disable=unidiomatic-typecheck
            for factory in reversed(Ports._factories):
                port = factory(ports[0])
                if port is not None:
                    Ports._ports[Ports._ports.index(ports[0])] = port
                    break
            else:
                raise PortError("Ports: unable to create port from origin '%s'" % ports[0].origin)
        else:
            assert isinstance(ports[0], Port)
            port = ports[0]
        return port

    @staticmethod
    def _load_ports():
        # type: () -> None
        print("Loading ports collection:")
        for category in Ports.categories:
            print("\tLoading category: %s" % category)
            for name in make_var(Ports.dir / category, "SUBDIR"):
                name = str(name)  # NOTE: remove in Python 3
                Ports._ports.append(PortStub(category, name, Ports.dir / category / name))

    @staticmethod
    def get_port_by_name(name):
        # type: (str) -> Port
        return Ports._get_port(lambda i: i.name == name)

    @staticmethod
    def get_port_by_origin(origin):
        # type: (str) -> Port
        return Ports._get_port(lambda i: i.origin == origin)

    @staticmethod
    def factory(factory):
        # type: (Callable[[PortStub], Port]) -> Callable[[PortStub], Port]
        Ports._factories.append(factory)
        return factory
