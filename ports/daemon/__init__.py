"""The daemon for interacting with ports through a WebAPI."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

__all__ = ['create_app', 'db']

db = SQLAlchemy(app)  # pylint: disable=C0103

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app
