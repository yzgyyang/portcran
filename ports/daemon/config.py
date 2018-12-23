"""Configuration object for SqlAlchemy."""
from os import environ

__all__ = ['Config']


class Config:  # pylint: disable=R0903
    """SqlAlchemy configuration class."""

    SLQALCHEMY_DATABASE_URI = environ.get('DATABASE_URL', 'sqlite:////var/lib/pathd/app.sqlite')

    SLQALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = environ.get('SECRET_KEY', 'd152598d74f494f956e0020becf21c3433fa8306da260a3e')
