========
PortCran
========

Generates FreeBSD Ports from CRAN packages.

Synopsis
========
portcran update <common options> [-o OUTDIR] name

Description
===========

Common options
--------------
The following common variables are recognised:

 -a,--address ADDRESS
	Use the specified address.  Defaults to <username>@<hostname>

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
