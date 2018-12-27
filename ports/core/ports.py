"""FreeBSD Ports Collection module.

This module provides an interface to interact with the FreeBSD Ports Collection, and means of discovering ports
therein.
"""
from os import environ
from typing import Callable, ClassVar, Dict, Iterator, List, Optional
from pathlib import Path
from .make import make, make_var
from .port import Port, PortError, PortStub

__all__ = ['Ports']


class Ports:
    """Representation of the FreeBSD Ports Collection."""

    _factories: ClassVar[List[Callable[[PortStub], Optional[Port]]]] = []
    _ports: ClassVar[List[PortStub]] = []
    _ports_by_name: ClassVar[Dict[str, Optional[int]]] = {}
    _ports_by_origin: ClassVar[Dict[str, int]] = {}
    dir: ClassVar[Path] = Path(environ.get('PORTSDIR', '/usr/ports'))

    categories = make_var(dir, 'SUBDIR')
    distdir = Path(environ.get('DISTDIR') or make(dir / 'Mk', '-VDISTDIR', '-fbsd.port.mk').strip())

    @staticmethod
    def _get(index: int) -> Port:
        if not Ports._ports:
            Ports._load_ports()
        portstub = Ports._ports[index]
        if isinstance(portstub, PortStub):
            for factory in reversed(Ports._factories):
                port = factory(portstub)
                if port is not None:
                    Ports._ports[index] = port
                    break
            else:
                raise PortError('Ports: unable to create port from origin \'%s\'' % portstub.origin)
        else:
            assert isinstance(portstub, Port)
            port = portstub
        return port

    @staticmethod
    def _load_ports() -> None:
        print('Loading ports collection:')
        index = 0
        for category in Ports.categories:
            print('\tLoading category: %s' % category)
            for name in make_var(Ports.dir / category, 'SUBDIR'):
                portstub = PortStub(category, name)
                Ports._ports.append(portstub)
                if name in Ports._ports_by_name:
                    Ports._ports_by_name[name] = None
                else:
                    Ports._ports_by_name[name] = index
                Ports._ports_by_origin[portstub.origin] = index
                index += 1

    @staticmethod
    def all() -> Iterator[PortStub]:
        """Return a sequence containing all port stubs."""
        if not Ports._ports:
            Ports._load_ports()
        return iter(Ports._ports)

    @staticmethod
    def get(name: Optional[str] = None, origin: Optional[str] = None) -> Port:
        """
        Get a port based on the specified criteria.

        The criteria must be only one of:
         - 'name': the name of the port
         - 'origin': the origin of the port
        """
        if None not in (name, origin):
            raise ValueError('only one criteria must be specified')

        if name is not None:
            index = Ports._ports_by_name[name]
        elif origin is not None:
            index = Ports._ports_by_origin[origin]
        else:
            raise ValueError('one criteria must be specified')

        if index is None:
            raise KeyError('multiple ports match the specified criteria')
        return Ports._get(index)

    @staticmethod
    def get_port_by_name(name: str) -> Port:
        """Get a port by the specified name."""
        return Ports.get(name=name)

    @staticmethod
    def get_port_by_origin(origin: str) -> Port:
        """Get a port by the specified port origin."""
        return Ports.get(origin=origin)

    @staticmethod
    def factory(factory: Callable[[PortStub], Optional[Port]]) -> Callable[[PortStub], Optional[Port]]:
        """
        Decorate a function to register it as being able to load a Port.

        The factory function will be passed a PortStub instance and, if the factory function can, return a Port
        instance.  If the factory function cannot load the given PortStub then None must be returned.
        """
        Ports._factories.append(factory)
        return factory
