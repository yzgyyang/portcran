from typing import Dict, Iterable, List, Tuple
from ports import Uses
from ports.core.internal import MakeDict

__all__ = ["PkgConfig", "ShebangFix"]


def create_uses(name: str) -> type:
    @Uses.register(name)
    class UsesClass(Uses):
        def __init__(self) -> None:
            super(UsesClass, self).__init__(name)
    return UsesClass

PkgConfig = create_uses("pkgconfig")


@Uses.register("shebangfix")
class ShebangFix(Uses):
    def __init__(self) -> None:
        super(ShebangFix, self).__init__("shebangfix")
        self.files: List[str] = []
        self.languages: Dict[str, Tuple[str, str]] = {}

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        if self.files:
            yield ("SHEBANG_FILES", self.files)
        if self.languages:
            yield ("SHEBANG_LANG", sorted(self.languages))
            for lang in sorted(self.languages):
                old_cmd, new_cmd = self.languages[lang]
                yield ("%s_OLD_CMD" % lang, (old_cmd,))
                yield ("%s_CMD" % lang, (new_cmd,))

    def load(self, variables: MakeDict) -> None:
        self.files = variables.pop("SHEBANG_FILES", default=[])
        for lang in variables.pop("SHEBANG_LANG", default=[]):
            old_cmd = variables.pop_value("%s_OLD_CMD" % lang)
            new_cmd = variables.pop_value("%s_CMD" % lang)
            assert old_cmd is not None and new_cmd is not None
            self.languages[lang] = (old_cmd, new_cmd)
