#!/bin/sh

pylint -d missing-docstring,locally-disabled,import-error ports portcran.py
mypy -i --py2 --strict --ignore-missing-imports ports portcran.py
