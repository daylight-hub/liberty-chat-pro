from pythonforandroid.recipe import CompiledComponentsPythonRecipe, Recipe


class CryptographyRecipe(CompiledComponentsPythonRecipe):
    """
    Cryptography 2.8 — matches the version used in Sideband 2.0.1's build
    environment (p4a 2024.1.21). This is a pure C extension with no Rust/PyO3
    dependency. Newer versions (41+) use Rust/PyO3 and fail on Android with
    p4a's Python embedding due to unresolvable stable-ABI symbols at dlopen.
    """
    name = 'cryptography'
    version = '2.8'
    url = 'https://github.com/pyca/cryptography/archive/{version}.tar.gz'
    depends = ['openssl', 'setuptools', 'cffi']
    call_hostpython_via_targetpython = False

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        openssl_recipe = Recipe.get_recipe('openssl', self.ctx)
        env['CFLAGS'] += openssl_recipe.include_flags(arch)
        env['LDFLAGS'] += openssl_recipe.link_dirs_flags(arch)
        env['LIBS'] = openssl_recipe.link_libs_flags()
        return env


recipe = CryptographyRecipe()
