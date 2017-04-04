#!/usr/bin/env python
from __future__ import absolute_import, division, print_function

from argparse import ArgumentParser
from re import search
from sys import argv
from urllib import urlretrieve
try:
    from urllib2 import urlopen
except ImportError:
    from urllib import urlopen  # type: ignore  # pylint: disable=ungrouped-imports
from ports import Platform, PortError, Ports
from ports.cran import Cran, CranPort
from ports.core.port import PortLicense  # pylint: disable=unused-import
from typing import BinaryIO, Iterable, List, Optional, Tuple  # pylint: disable=unused-import


__author__ = "Davd Naylor <dbn@FreeBSD.org>"
__license__ = "BSD (FreeBSD)"
__summary__ = "Generates FreeBSD Ports from CRAN packages"
__version__ = "0.1.4"


def make_cran_port(name, portdir=None):
    # type: (str, Optional[str]) -> CranPort
    print("Checking for latest version...")
    site_page = urlopen("http://cran.r-project.org/package=%s" % name).read()
    version = search(r"<td>Version:</td>\s*<td>(.*?)</td>", site_page).group(1)
    distfile = Ports.distdir / ("%s_%s.tar.gz" % (name, version))
    if not distfile.exists():  # pylint: disable=no-member
        print("Fetching package source...")
        urlretrieve("https://cran.r-project.org/src/contrib/%s" % distfile.name, distfile)  # pylint: disable=no-member
    return CranPort.create(name, distfile, portdir)


def diff(left, right):
    # type: (Iterable[str], Iterable[str]) -> Tuple[List[str], bool, List[str]]
    left = list(left)
    right = list(right)
    old = [i for i in left if i not in right]
    new = [i for i in right if i not in left]
    left = [i for i in left if i not in old]
    right = [i for i in right if i not in new]
    return old, left == right, new


def log_depends(log, depend, difference):
    # type: (BinaryIO, str, Tuple[List[str], bool, List[str]]) -> None
    old, common, new = difference
    if not common:
        log.write(" - order %s dependencies lexicographically on origin\n" % depend)
    if len(old) > 0:
        log.write(" - remove unused %s dependencies:\n" % depend)
        for i in sorted(old):
            log.write("   - %s\n" % i)
    if len(new) > 0:
        log.write(" - add new %s dependencies:\n" % depend)
        for i in sorted(new):
            log.write("   - %s\n" % i)


def log_uses(log, difference):
    # type: (BinaryIO, Tuple[List[str], bool, List[str]]) -> None
    old, common, new = difference
    if not common:
        log.write(" - sort cran uses arguments lexicographically\n")
    for arg in old:
        if arg == "auto-plist":
            log.write(" - manually generate pkg-plist\n")
        elif arg == "compiles":
            log.write(" - port no longer needs to compile\n")
        else:
            raise PortError("Log: unknown cran argument: %s" % arg)
    for arg in new:
        if arg == "auto-plist":
            log.write(" - automatically generate pkg-plist\n")
        elif arg == "compiles":
            log.write(" - mark port as needing to compile\n")
        else:
            raise PortError("Log: unknown cran argument: %s" % arg)


def log_license(log, old, new):
    # type: (BinaryIO, PortLicense, PortLicense) -> None
    if list(old) != list(sorted(new)):
        log.write(" - update license to: %s\n" % " ".join(sorted(new)))
    elif old.combination != new.combination:
        if new.combination is None:
            log.write(" - remove license combination\n")
        else:
            log.write(" - update license combination\n")


def generate_update_log(old, new):
    # type: (CranPort, CranPort) -> None
    assert (old.portversion or old.distversion) != new.distversion
    with open(new.portdir / "commit.svn", "w") as log:
        log.write("%s: updated to version %s\n\n" % (new.origin, new.distversion))
        if old.portrevision is not None:
            log.write(" - removed PORTREVISION due to version bump\n")

        if old.maintainer != new.maintainer:
            log.write(" - update maintainer\n")
        if old.comment != new.comment:
            log.write(" - updated comment to align with CRAN package\n")

        if list(sorted(old.license)) != list(sorted(new.license)) or old.license.combination != new.license.combination:
            log.write(" - updated license to align with CRAN package\n")
        if old.license.file is None and new.license.file is not None:
            log.write(" - added license file from CRAN package\n")
        elif old.license.file is not None and new.license.file is None:
            log.write(" - removed license file (no longer in CRAN package)\n")

        for depend in ("build", "lib", "run", "test"):
            old_depends = getattr(old.depends, depend)
            new_depends = getattr(new.depends, depend)
            log_depends(log, depend, diff([i.origin for i in old_depends], sorted(i.origin for i in new_depends)))

        if old.no_arch != new.no_arch and "compiles" not in new.uses[Cran]:
            log.write(" - set NO_ARCH as port does not compile\n")

        if new.distversion in new.changelog:
            assert new.distversion is not None
            log.write(" - changelog:\n")
            for line in new.changelog[new.distversion]:
                log.write("   -")
                length = 4
                for word in line.split(" "):
                    length += len(word) + 1
                    if length > 75:
                        log.write("\n    ")
                        length = 5 + len(word)
                    log.write(" " + word)
                log.write("\n")
        else:
            log.write(" - no changelog provided\n")

        log.write("\nGenerated by:\tportcran (%s)\n" % __version__)


def update():
    # type: () -> None
    parser = ArgumentParser()
    parser.add_argument("name", help="Name of the CRAN package")
    parser.add_argument("-o", "--output", help="Output directory")

    parser.add_argument("-a", "--address", help="Creator/maintainer's e-mail address")

    args = parser.parse_args()

    if args.address is not None:
        Platform.address = args.address

    port = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + args.name)
    assert isinstance(port, CranPort)
    cran = make_cran_port(args.name, args.output)
    cran.generate()
    generate_update_log(port, cran)


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
