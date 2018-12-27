"""Special handling of FreeBSD Port variables."""
from .core.make import MakeDict
from .core import Port
from .cran import CranPort
from .uses import Gnome


@Port.load_hack
def gnome(port: Port, variables: MakeDict) -> None:
    """Handle 'USE_GNOME' without 'USES=gnome'."""
    if 'USE_GNOME' in variables:
        port.uses[Gnome].load(variables)


@Port.load_hack
def cran_distname(port: Port, variables: MakeDict) -> None:  # pylint: disable=W0613
    """Handle bad DISTNAME for CRAN port mvtnorm."""
    if isinstance(port, CranPort) and port.distname not in ('${PORTNAME}_${DISTVERSION}', '${PORTNAME}_${PORTVERSION}'):
        if port.portversion is not None:
            port.distversion = port.portversion
            del port.portversion
        port.distname = '${PORTNAME}_${DISTVERSION}'
