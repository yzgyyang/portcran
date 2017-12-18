from os import environ
from typing import Callable, ClassVar, List, Optional
from plumbum.cmd import make
from plumbum.path import LocalPath
from ports.core.internal import make_var
from ports.core.port import CyclicalDependencyError, Port, PortError, PortStub

__all__ = ["Ports"]


class Ports(object):
    _factories: ClassVar[List[Callable[[PortStub], Optional[Port]]]] = []
    _ports: ClassVar[List[PortStub]] = []
    _loading: ClassVar[List[PortStub]] = []
    dir: ClassVar[LocalPath] = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make_var(dir, "SUBDIR")
    distdir = LocalPath(make["-C", dir / "Mk", "-VDISTDIR", "-fbsd.port.mk"]().strip())

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
            if portstub in Ports._loading:
                raise CyclicalDependencyError(portstub)
            try:
                Ports._loading.append(portstub)
                for factory in reversed(Ports._factories):
                    port = factory(portstub)
                    if port is not None:
                        Ports._ports[Ports._ports.index(ports[0])] = port
                        break
                else:
                    raise PortError("Ports: unable to create port from origin '%s'" % ports[0].origin)
            except CyclicalDependencyError as err:
                err.add(portstub)
                raise
            finally:
                Ports._loading.remove(portstub)
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
        return Ports._get_port(lambda i: i.name == name)

    @staticmethod
    def get_port_by_origin(origin: str) -> Port:
        return Ports._get_port(lambda i: i.origin == origin)

    @staticmethod
    def factory(factory: Callable[[PortStub], Optional[Port]]) -> Callable[[PortStub], Optional[Port]]:
        Ports._factories.append(factory)
        return factory
