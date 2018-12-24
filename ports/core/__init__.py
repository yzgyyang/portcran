"""Core architecture representing the FreeBSD Ports Collection."""
from .dependency import Dependency
from .make import MakeDict
from .platform import Platform
from .port import Port, PortDepends, PortError, PortLicense, PortStub
from .ports import Ports
from .uses import Uses

__all__ = [
    "Dependency",
    "MakeDict",
    "Platform",
    "Port",
    "PortDepends",
    "PortError",
    "PortLicense",
    "PortStub",
    "Ports",
    "Uses"
]
