"""Special handling of FreeBSD Port variables."""
from .core.make import MakeDict
from .core import Port
from .uses import Gnome


@Port.load_hack
def gnome(port: Port, variables: MakeDict) -> None:
    """Handle 'USE_GNOME' without 'USES=gnome'."""
    if 'USE_GNOME' in variables:
        port.uses[Gnome].load(variables)
