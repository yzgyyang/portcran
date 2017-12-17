#!/usr/bin/env python3

from distutils.core import setup

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
