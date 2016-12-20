from __future__ import absolute_import, division, print_function

from ports import Uses
from ports.core.internal import MakeDict  # pylint: disable=unused-import
from typing import Dict, Iterable, List, Tuple  # pylint: disable=unused-import

__all__ = ["PkgConfig", "ShebangFix"]


def create_uses(name):
    # type: (str) -> type
    @Uses.register(name)
    class UsesClass(Uses):
        def __init__(self):
            # type: () -> None
            super(UsesClass, self).__init__(name)
    return UsesClass

PkgConfig = create_uses("pkgconfig")


@Uses.register("shebangfix")
class ShebangFix(Uses):
    def __init__(self):
        # type: () -> None
        super(ShebangFix, self).__init__("shebangfix")
        self.files = []  # type: List[str]
        self.languages = {}  # type: Dict[str, Tuple[str, str]]

    def generate(self):
        # type: () -> Iterable[Tuple[str, Iterable[str]]]
        if self.files:
            yield ("SHEBANG_FILES", self.files)
        if self.languages:
            yield ("SHEBANG_LANG", sorted(self.languages.keys()))
            for lang in sorted(self.languages.keys()):
                old_cmd, new_cmd = self.languages[lang]
                yield ("%s_OLD_CMD" % lang, (old_cmd,))
                yield ("%s_CMD" % lang, (new_cmd,))

    def load(self, variables):
        # type: (MakeDict) -> None
        self.files = variables.pop("SHEBANG_FILES", default=[])
        for lang in variables.pop("SHEBANG_LANG", default=[]):
            old_cmd = variables.pop_value("%s_OLD_CMD" % lang)
            new_cmd = variables.pop_value("%s_CMD" % lang)
            self.languages[lang] = (old_cmd, new_cmd)
