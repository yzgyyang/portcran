#!/usr/bin/env python
from __future__ import absolute_import, division, print_function

from argparse import ArgumentParser
from re import compile as recompile, search
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
from ports.core.internal import Stream
from ports.core.port import PortLicense  # pylint: disable=unused-import
from typing import BinaryIO, Iterable, Tuple  # pylint: disable=unused-import


__author__ = "Davd Naylor <dbn@FreeBSD.org>"
__license__ = "BSD (FreeBSD)"
__summary__ = "Generates FreeBSD Ports from CRAN packages"
__version__ = "0.1.3"


def make_cran_port(name, portdir=None):
    # type: (str, LocalPath) -> CranPort
    print("Cheching for latest version...")
    site_page = urlopen("http://cran.r-project.org/package=%s" % name).read()
    version = search(r"<td>Version:</td>\s*<td>(.*?)</td>", site_page).group(1)
    distfile = Ports.distdir / ("%s_%s.tar.gz" % (name, version))
    if not distfile.exists():  # pylint: disable=no-member
        print("Fetching package source...")
        urlretrieve("https://cran.r-project.org/src/contrib/%s" % distfile.name, distfile)  # pylint: disable=no-member
    cran = CranPort("math", name, portdir)
    try:
        port = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + name)
        cran.category = port.categories[0]
        cran.categories = port.categories
        cran.maintainer = port.maintainer
    except PortError:
        pass
    with TarFile.open(str(distfile), "r:gz") as distfile:
        desc = Stream(i.rstrip('\n') for i in distfile.extractfile("%s/DESCRIPTION" % name).readlines())
        cran.changelog = parse_changelog(distfile, name)
    identifier = recompile(r"^[a-zA-Z/@]+:")
    while desc.has_current:
        key, value = desc.current.split(":", 1)
        desc.next()
        value = value.strip() + "".join(" " + i.strip() for i in desc.take_while(lambda l: not identifier.match(l)))
        cran.parse(key, value, desc.line)  # type: ignore
    return cran


def parse_changelog(distfile, name):
    # type: (TarFile, str) -> Dict[str, List[str]]
    try:
        changelog = Stream(distfile.extractfile("%s/ChangeLog" % name).readlines(), lambda x: x.strip(), line=0)
    except NameError:
        return {}
    log = {}
    version = None
    version_identifier = recompile(r"^\* DESCRIPTION \(Version\): New version is (.*)\.$")
    section = recompile(r"^\d{4}-\d{2}-\d{2} .* <.*>$")
    while changelog.next():
        for line in changelog.take_while(lambda l: not version_identifier.match(l)):
            if section.match(line):
                continue
            if line:
                if version is None:
                    raise PortError("ChangeLog contains unrecognised text")
                if line[0] in ('*', '('):
                    log[version].append(line[2:])
                else:
                    log[version][-1] += " " + line
        if changelog.has_current:
            version = version_identifier.search(changelog.current).group(1)
            assert version not in log
            log[version] = []
    return log


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
    if len(old):
        log.write(" - remove unused %s dependencies:\n" % depend)
        for i in sorted(old):
            log.write("   - %s\n" % i)
    if len(new):
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
        if old.license.file is None and new.license.file:
            log.write(" - added license file from CRAN package\n")
        elif old.license.file and new.license.file is None:
            log.write(" - removed license file (no longer in CRAN package)\n")

        for depend in ("build", "lib", "run", "test"):
            old_depends = getattr(old.depends, depend)
            new_depends = getattr(new.depends, depend)
            log_depends(log, depend, diff([i.origin for i in old_depends], sorted(i.origin for i in new_depends)))

        if old.no_arch != new.no_arch and "compiles" not in new.uses[Cran]:
            log.write(" - set NO_ARCH as port does not compile\n")

        if new.distversion in new.changelog:
            log.write(" - changelog:\n")
            for line in new.changelog[new.distname]:
                log.write("   -")
                length = 4
                for word in line.split(" "):
                    length += len(word) + 1
                    if length > 75:
                        log.write("\n    ")
                        length = 5 + len(word)
                    log.write(" " + word)
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

    portdir = None if args.output is None else LocalPath(args.output)
    port = Ports.get_port_by_name(Cran.PKGNAMEPREFIX + args.name)
    assert isinstance(port, CranPort)
    cran = make_cran_port(args.name, portdir)
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
