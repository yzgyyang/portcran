from os import getuid
from pwd import getpwuid
from socket import gethostname

__all__ = ["Platform"]


class Platform(object):
    # pylint: disable=too-few-public-methods
    _passwd = getpwuid(getuid())

    address = "%s@%s" % (_passwd.pw_name, gethostname())

    page_width = 80

    tab_width = 8
