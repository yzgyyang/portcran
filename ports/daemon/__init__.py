"""The daemon for interacting with ports through a WebAPI."""
from typing import List, Tuple
from flask import Blueprint, Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from ..core import Port, Ports
from ..cran import Cran

__all__ = ['create_app', 'bp', 'db']

bp = Blueprint('portd', __name__)  # pylint: disable=C0103

db = SQLAlchemy()  # pylint: disable=C0103


def sync_ports():
    """Syncronise the Port database with the FreeBSD Ports Collection."""
    from .models import Port as ModelPort

    ports: List[Tuple[Port, str]] = []
    for portstub in Ports.all():
        if portstub.name.startswith(Cran.PKGNAMEPREFIX):
            ports.append((Ports.get_port_by_origin(portstub.origin), 'cran'))
    model_ports = set(ModelPort.query.all())

    for port, source in ports:
        match = [model_port for model_port in model_ports if model_port.origin == port.origin]
        assert len(match) <= 1
        if match:
            model_port = match[0]
            assert model_port.source == source
            model_ports.remove(model_port)
            for attr in ('name', 'version', 'maintainer', 'origin'):
                if getattr(model_port, attr) != getattr(port, attr):
                    setattr(model_port, attr, getattr(port, attr))
        else:
            db.session.add(ModelPort(
                name=port.name,
                version=port.version,
                maintainer=port.maintainer,
                origin=port.origin,
                source=source,
                latest_source=None,
            ))
        for model_port in model_ports:
            db.session.remove(model_port)
    db.session.commit()


def create_app() -> Flask:
    """Create a WebAPI Flask Application for portd."""
    from . import routes

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(bp)

    sync_ports()

    return app
