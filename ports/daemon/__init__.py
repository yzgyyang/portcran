"""The daemon for interacting with ports through a WebAPI."""
from flask import Blueprint, Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

__all__ = ['create_app', 'bp', 'db']

bp = Blueprint('portd', __name__)  # pylint: disable=C0103

db = SQLAlchemy()  # pylint: disable=C0103


def create_app(config_class=Config) -> Flask:
    """Create a WebAPI Flask Application for portd."""
    from .models import sync_ports
    from . import routes

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    app.register_blueprint(bp)

    sync_ports(app)

    return app
