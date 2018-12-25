"""The object models defining the port objects."""
from typing import Dict, Optional, Union
from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from . import db

__all__ = ['Json', 'Patch', 'Port']


Json = Dict[str, Optional[Union[int, str]]]


class Port(db.Model):  # pylint: disable=R0903
    """Object model describing a FreeBSD Port from a specified source."""

    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    version = Column(String(16))
    maintainer = Column(String(256))
    source = Column(String(4))
    latest_version = Column(String(16))
    origin = Column(String(256))
    patches = relationship('Patch', back_populates='port')

    def as_json(self) -> Json:
        """Return this Port as a JSON friendly dictionary object."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "maintainer": self.maintainer,
            "source": self.source,
            "latest_version": self.latest_version,
            "origin": self.origin,
            "patch": None,
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
