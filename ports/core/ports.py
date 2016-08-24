from __future__ import absolute_import, division, print_function

from os import environ
from plumbum.cmd import make
from plumbum.path import LocalPath
from ports.core.port import PortException, PortStub

__all__ = ["Ports"]


class Ports(object):
    _ports = []  # type: List[PortStub]
    dir = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make["-C", dir, "-VSUBDIR"]().split()
    distdir = LocalPath(make["-C", dir / "Mk", "-fbsd.port.mk", "-VDISTDIR"]().strip())

    @staticmethod
    def get_port_by_name(name):
        # type: (str) -> PortStub
        if not len(Ports._ports):
            for category in Ports.categories:
                for name in make["-C", Ports.dir / category, "-VSUBDIR"]().split():
                    Ports._ports.append(PortStub(category, name, Ports.dir / category / name))
        ports = [i for i in Ports._ports if i.name == name]
        if not len(ports):
            raise PortException("Ports: no port with name '%s' in collection" % name)
        if len(ports) > 1:
            raise PortException("Ports: multiple ports with name '%s' in collection" % name)
        return ports[0]
