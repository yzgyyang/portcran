"""The daemon for interacting with ports through a WebAPI."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from .routes import define_routes

__all__ = ['create_app', 'db']


db = SQLAlchemy()  # pylint: disable=C0103


def create_app() -> Flask:
    """Create a WebAPI Flask Application for portd."""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    db.create_all()
    define_routes(app)
    return app
