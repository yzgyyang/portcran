"""The object models defining the port objects."""
from typing import Dict, Optional, Union
from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from . import db
from ..core import Ports
from ..cran import Cran

__all__ = ['Json', 'Patch', 'Port']


Json = Dict[str, Optional[Union[int, str]]]


def sync_ports():
    """
    Syncronise the Port database with the FreeBSD Ports Collection.

    This function must be run within a Flask.app_context().
    """
    ports = (
        (Ports.get_port_by_origin(portstub.origin), 'cran') for portstub in Ports.all()
        if portstub.name.startswith(Cran.PKGNAMEPREFIX)
    )
    model_ports = set(Port.query.all())

    for port, source in ports:
        match = [
            model_port for model_port in model_ports
            if model_port.name == port.name and model_port.source == source
        ]
        assert len(match) <= 1
        if match:
            model_port = match[0]
            assert model_port.source == source
            model_ports.remove(model_port)
            for attr in ('name', 'version', 'maintainer', 'origin'):
                value = getattr(port, attr)
                if getattr(model_port, attr) != value:
                    setattr(model_port, attr, value)
                    print('%s (%s): update %s to \'%s\'' % (port.name, source, attr, value))
        else:
            print('%s (%s): add port' % (port.name, source))
            db.session.add(Port(
                name=port.name,
                version=port.version,
                maintainer=port.maintainer,
                origin=port.origin,
                source=source,
                latest_version=None,
            ))
        for model_port in model_ports:
            print('%s (%s): remove port' % (port.nsme, source))
            db.session.remove(model_port)
    db.session.commit()


class Port(db.Model):  # pylint: disable=R0903
    """Object model describing a FreeBSD Port from a specified source."""

    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    version = Column(String(16))
    maintainer = Column(String(256))
    origin = Column(String(256))
    source = Column(String(4))
    latest_version = Column(String(16))
    patches = relationship('Patch', back_populates='port')

    def as_json(self) -> Json:
        """Return this Port as a JSON friendly dictionary object."""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'maintainer': self.maintainer,
            'source': self.source,
            'latest_version': self.latest_version,
            'origin': self.origin,
            'patch': None,
        }


class Patch(db.Model):  # pylint: disable=R0903
    """Object model describing a change to a Port."""

    id = Column(Integer, primary_key=True)
    action = Column(String(6))
    log = Column(String)
    status = Column(String(8))
    error = Column(String)
    diff = Column(String(256))
    port_id = Column(Integer, ForeignKey('port.id'))
    port = relationship('Port', back_populates='patches')
