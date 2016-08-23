from __future__ import absolute_import, division, print_function

from os import environ
from plumbum.cmd import make
from plumbum.path import LocalPath

__all__ = ["Ports"]


class Ports(object):
    # pylint: disable=too-few-public-methods
    dir = LocalPath(environ.get("PORTSDIR", "/usr/ports"))

    categories = make["-C", dir, "-VSUBDIR"]().split()
    distdir = LocalPath(make["-C", dir / "Mk", "-fbsd.port.mk", "-VDISTDIR"]().strip())
