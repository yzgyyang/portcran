========
PortCran
========

Generates FreeBSD Ports from CRAN packages.

Synopsis
========
portcran create <common options> [-c CATEGORIES] [-p PORTSDIR] name
portcran update <common options> [-o OUTDIR] name

Description
===========

Common options
--------------
The following common variables are recognised:

 -a,--address ADDRESS
	Use the specified address.  Defaults to <username>@<hostname>

 -h,--help
    Show the help message and exit

Create options
--------------
The following create specific options are available:

 -c,--CATEGORIES
   Comma separated list of the port categories.  Defaults to math

 -p,--portsdir PORTSDIR
   Output ports directory.  Defaults to $(PORTDIR}


Update options
--------------
The following update specific options are available:

 -o OUTDIR
	Use the specified output directory for when updating the port.  Defaults to
	${PORTDIR}/${category}/R-cran-${name}

Environment Variables
=====================
The following environment variables are recognised:

 PORTDIR
	The directory of the FreeBSD Ports.  Defaults to /usr/ports.
