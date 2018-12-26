from typing import Dict, Iterable, List, Tuple
from .core import MakeDict, Uses

__all__ = ['Gnome', 'MySQL', 'Perl5', 'PgSQL', 'PkgConfig', 'ShebangFix']


def create_uses(name: str, use=False) -> type:
    @Uses.register(name)
    class UsesClass(Uses):
        def __init__(self) -> None:
            super(UsesClass, self).__init__(name)
            if use:
                self.components: List[str] = []

        if use:
            use_name = 'USE_%s' % name.upper() if use else ''

            def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
                if self.components:
                    yield (self.use_name, self.components)

            def load(self, variables: MakeDict) -> None:
                self.components = variables.pop(self.use_name, default=[])

    return UsesClass


Gnome = create_uses('gnome', use=True)
MySQL = create_uses('mysql')
Perl5 = create_uses('perl5', use=True)
PgSQL = create_uses('pgsql')
PkgConfig = create_uses('pkgconfig')


@Uses.register('shebangfix')
class ShebangFix(Uses):
    def __init__(self) -> None:
        super(ShebangFix, self).__init__('shebangfix')
        self.files: List[str] = []
        self.languages: Dict[str, Tuple[str, str]] = {}

    def generate(self) -> Iterable[Tuple[str, Iterable[str]]]:
        if self.files:
            yield ('SHEBANG_FILES', self.files)
        if self.languages:
            yield ('SHEBANG_LANG', sorted(self.languages))
            for lang in sorted(self.languages):
                old_cmd, new_cmd = self.languages[lang]
                yield ('%s_OLD_CMD' % lang, (old_cmd,))
                yield ('%s_CMD' % lang, (new_cmd,))

    def load(self, variables: MakeDict) -> None:
        self.files = variables.pop('SHEBANG_FILES', default=[])
        for lang in variables.pop('SHEBANG_LANG', default=[]):
            old_cmd = variables.pop_value('%s_OLD_CMD' % lang)
            new_cmd = variables.pop_value('%s_CMD' % lang)
            assert old_cmd is not None and new_cmd is not None
            self.languages[lang] = (old_cmd, new_cmd)
