"""The object models defining the port objects."""
from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from . import db

__all__ = ['Patch', 'Port']


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
