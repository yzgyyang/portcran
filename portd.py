"""Portd daemon."""
from cProfile import Profile
from os import environ
from pstats import Stats

if __name__ == '__main__':
    environ['DISTDIR'] = '/tmp'
    environ['FLASK_APP'] = 'ports.daemon'
    environ['MAKE'] = 'bmake'
    environ['PORTSDIR'] = '/Users/davidnaylor/Projects/ports'
    from ports.daemon import create_app
    p = Profile()
    p.enable()
    try:
        create_app()
    finally:
        p.disable()
        Stats(p).sort_stats('cumulative').print_stats(30)
