#!/bin/sh

pylint-3.6 -d missing-docstring,locally-disabled,import-error ports portcran.py
mypy -i --strict --ignore-missing-imports ports portcran.py
