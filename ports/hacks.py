"""Special handling of FreeBSD Port variables."""
from .core.make import MakeDict
from .core import Port
from .uses import Gnome


@Port.load_hack
def gnome(port: Port, variables: MakeDict) -> None:
    """Handle 'USE_GNOME' without 'USES=gnome'."""
    if 'USE_GNOME' in variables:
        port.uses[Gnome].load(variables)


@Port.load_hack
def mvtnorm(port: Port, variables: MakeDict) -> None:
    """Handle bad DISTNAME for CRAN port mvtnorm."""
    if port.name == 'R-cran-mvtnorm':
        port.distversion = port.portversion
        port.distname = '${PORTNAME}_${DISTVERSION}'
        del port.portversion
