#!/usr/bin/env python3
"""Setup script for Portd."""
import sys
from distutils.core import setup

if sys.version_info < (3, 6):
    sys.exit('Python version >= 3.6 required')

setup(
    name='portcran',
    version='0.1.9',
    author='David Naylor',
    author_email='dbn@FreeBSD.org',
    packages=[
        'ports.core',
        'ports',
        'ports.cran',
        'ports.daemon.models',
        'ports.daemon',
    ],
    scripts=['portcran.py'],
    license='LICENSE.txt',
    description='Generates FreeBSD Ports from CRAN packages',
    long_description=open('README.txt').read(),
    install_requires=[
        'flask',
        'flask_sqlalchemy',
        'plumbum',
    ],
)
