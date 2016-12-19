from __future__ import absolute_import, division, print_function

from ports import Uses

__all__ = ["PkgConfig", "ShebangFix"]


def create_uses(name):
    @Uses.register(name)
    class UsesClass(Uses):
        def __init__(self):
            # type: () -> None
            super(UsesClass, self).__init__(name)
    return UsesClass

PkgConfig = create_uses("pkgconfig")
ShebangFix = create_uses("shebangfix")
