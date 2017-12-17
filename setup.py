#!/usr/bin/env python3

from distutils.core import exit, setup
from sys import version_info

if sys.version_info < (3, 6):
    exit("Python version >= 3.6 required")

setup(
    name="portcran",
    version="0.1.5",
    author="David Naylor",
    author_email="dbn@FreeBSD.org",
    packages=["ports.core", "ports", "ports.cran"],
    scripts=["portcran.py"],
    license="LICENSE.txt",
    description="Generates FreeBSD Ports from CRAN packages",
    long_description=open("README.txt").read(),
)
