#!/usr/bin/env python
from __future__ import absolute_import, division, print_function

from argparse import ArgumentParser
from re import match, search
from sys import argv
from tarfile import TarFile
from urllib import urlretrieve
try:
    from urllib2 import urlopen
except ImportError:
    from urllib import urlopen  # type: ignore  # pylint: disable=ungrouped-imports
from plumbum.path import LocalPath
from ports import Platform, PortError, Ports
from ports.cran import Cran, CranPort
from typing import Callable, Iterable  # pylint: disable=unused-import


class Stream(object):
    def __init__(self, objects):
        # type: (Iterable[str]) -> None
        self._objects = list(objects)
        self.line = 1

    @property
    def current(self):
        # type: () -> str
        return self._objects[self.line - 1]

    @property
    def has_current(self):
        # type: () -> bool
        return self.line != -1

    def next(self):
        # type: () -> bool
        if 0 <= self.line < len(self._objects):
            self.line += 1
            return True
        self.line = -1
        return False

    def take_until(self, condition):
        # type: (Callable[[str], bool]) -> Iterable[str]
        while self.next() and not condition(self.current):
            yield self.current


def match_key(line):
    # type: (str) -> bool
    return bool(match("^[a-zA-Z/@]+:", line))


def make_cran_port(name, portdir=None):
    # type: (str, LocalPath) -> CranPort
    print("Cheching for latest version...")
    site_page = urlopen("http://cran.r-project.org/package=%s" % name).read()
    version = search(r"<td>Version:</td>\s*<td>(.*?)</td>", site_page).group(1)
    distfile = Ports.distdir / ("%s_%s.tar.gz" % (name, version))
    if not distfile.exists():  # pylint: disable=no-member
        print("Fetching package source...")
        urlretrieve("https://cran.r-project.org/src/contrib/%s" % distfile.name, distfile)  # pylint: disable=no-member
    try:
        categories = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + name).categories
    except PortError:
        categories = ["make"]
    cran = CranPort(categories[0], name, portdir)
    if len(categories) > 1:
        cran.categories = categories
    with TarFile.open(str(distfile), "r:gz") as distfile:
        desc = Stream(i.rstrip('\n') for i in distfile.extractfile("%s/DESCRIPTION" % name).readlines())
    while desc.has_current:
        line = desc.current
        key, value = line.split(":", 1)
        value = value.strip() + "".join(" " + i.strip() for i in desc.take_until(match_key))
        cran.parse(key, value, desc.line)  # type: ignore
    return cran


def update():
    # type: () -> None
    parser = ArgumentParser()
    parser.add_argument("name", help="Name of the CRAN package")
    parser.add_argument("-o", "--output", help="Output directory")

    parser.add_argument("-a", "--address", help="Creator/maintainer's e-mail address")

    args = parser.parse_args()

    if args.address is not None:
        Platform.address = args.address

    portdir = None if args.output is None else LocalPath(args.output)
    cran = make_cran_port(args.name, portdir)
    cran.generate()


def main():
    # type: () -> None
    if len(argv) == 1:
        print("usage: portcran update [-o OUTPUT] name")
        exit(2)
    action = argv.pop(1)
    if action == "update":
        update()

if __name__ == "__main__":
    main()
