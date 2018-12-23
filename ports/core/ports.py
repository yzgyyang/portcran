"""FreeBSD Ports Collection module.

This module provides an interface to interact with the FreeBSD Ports Collection, and means of discovering ports
therein.
"""
from os import environ
from typing import Callable, ClassVar, List, Optional
from plumbum import local
from plumbum.path import LocalPath
from .make import make_var
from .port import Port, PortError, PortStub

__all__ = ["Ports", "MAKE"]


MAKE = local[environ.get("MAKE", default="make")]


class Ports(object):
    """Representation of the FreeBSD Ports Collection."""

    _factories: ClassVar[List[Callable[[PortStub], Optional[Port]]]] = []
    _ports: ClassVar[List[PortStub]] = []
    dir: ClassVar[LocalPath] = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make_var(dir, "SUBDIR")
    distdir = LocalPath(MAKE("-C", dir / "Mk", "-VDISTDIR", "-fbsd.port.mk").strip())

    @staticmethod
    def _get_port(selector: Callable[[PortStub], bool]) -> Port:
        if not Ports._ports:
            Ports._load_ports()
        ports = [i for i in Ports._ports if selector(i)]
        if not ports:
            raise PortError("Ports: no port matches requirement")
        if len(ports) > 1:
            raise PortError("Ports: multiple ports match requirement")
        if isinstance(ports[0], PortStub):
            portstub = ports[0]
            for factory in reversed(Ports._factories):
                port = factory(portstub)
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
    def _load_ports() -> None:
        print("Loading ports collection:")
        for category in Ports.categories:
            print("\tLoading category: %s" % category)
            for name in make_var(Ports.dir / category, "SUBDIR"):
                Ports._ports.append(PortStub(category, name))

    @staticmethod
    def get_port_by_name(name: str) -> Port:
        """Get a port by the specified name."""
        return Ports._get_port(lambda i: i.name == name)

    @staticmethod
    def get_port_by_origin(origin: str) -> Port:
        """Get a port by the specified port origin."""
        return Ports._get_port(lambda i: i.origin == origin)

    @staticmethod
    def factory(factory: Callable[[PortStub], Optional[Port]]) -> Callable[[PortStub], Optional[Port]]:
        """
        Decorate a function to register it as being able to load a Port.

        The factory function will be passed a PortStub instance and, if the factory function can, return a Port
        instance.  If the factory function cannot load the given PortStub then None must be returned.
        """
        Ports._factories.append(factory)
        return factory
