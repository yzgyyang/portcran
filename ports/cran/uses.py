from __future__ import absolute_import, division, print_function

from ports import Uses
from typing import List  # pylint: disable=unused-import

__all__ = ["Cran"]


@Uses.register("cran")
class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self):
        # type: () -> None
        super(Cran, self).__init__("cran")

    def get_variable(self, name):
        # type: (str) -> List[str]
        if name == "PKGNAMEPREFIX":
            return [Cran.PKGNAMEPREFIX]
