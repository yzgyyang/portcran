from typing import List, Optional
from ..core import Uses

__all__ = ["Cran"]


@Uses.register("cran")
class Cran(Uses):
    PKGNAMEPREFIX = "R-cran-"

    def __init__(self) -> None:
        super(Cran, self).__init__("cran")

    def get_variable(self, name: str) -> Optional[List[str]]:
        if name == "PKGNAMEPREFIX":
            return [Cran.PKGNAMEPREFIX]
        return None
