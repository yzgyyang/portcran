"""Portd daemon."""
from os import environ
import yappi

if __name__ == '__main__':
    environ['DISTDIR'] = '/tmp'
    environ['FLASK_APP'] = 'ports.daemon'
    environ['MAKE'] = 'bmake'
    environ['PORTSDIR'] = '/Users/davidnaylor/Projects/ports'
    from ports.daemon import create_app
    yappi.start()
    try:
        create_app()
    finally:
        yappi.stop()
        yappi.get_func_stats().save('callgrind.out', 'CALLGRIND')
        yappi.clear_stats()
