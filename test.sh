#!/bin/sh

pylint -d missing-docstring,locally-disabled,import-error ports portcran.py
mypy --py2 --silent-imports --disallow-untyped-calls --disallow-untyped-defs ports portcran.py
