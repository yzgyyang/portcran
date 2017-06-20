from __future__ import absolute_import, division, print_function

from typing import List, Optional  # pylint: disable=unused-import
from ports import Uses

__all__ = ["Cran"]


@Uses.register("cran")
class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self):
        # type: () -> None
        super(Cran, self).__init__("cran")

    def get_variable(self, name):
        # type: (str) -> Optional[List[str]]
        if name == "PKGNAMEPREFIX":
            return [Cran.PKGNAMEPREFIX]
        return None
