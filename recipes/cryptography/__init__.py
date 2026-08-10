from pythonforandroid.recipe import RustCompiledComponentsRecipe
from os.path import join


class CryptographyRecipe(RustCompiledComponentsRecipe):

    name = 'cryptography'
    # 43.0.3 is the last release whose Rust/PyO3 layer is compatible with
    # Python 3.11 on Android. Version 44+ dropped _Py_NoneStruct usage but
    # 46.x re-introduced Python-3.12-specific ABI symbols that our 3.11
    # build does not export, causing dlopen failures at runtime.
    version = '43.0.3'
    url = 'https://github.com/pyca/cryptography/archive/refs/tags/{version}.tar.gz'
    depends = ['openssl', 'cffi']

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        openssl_build_dir = self.get_recipe('openssl', self.ctx).get_build_dir(arch.arch)
        build_target = self.RUST_ARCH_CODES[arch.arch].upper().replace("-", "_")
        openssl_include = "{}_OPENSSL_INCLUDE_DIR".format(build_target)
        openssl_libs = "{}_OPENSSL_LIB_DIR".format(build_target)
        env[openssl_include] = join(openssl_build_dir, 'include')
        env[openssl_libs] = join(openssl_build_dir)
        return env


recipe = CryptographyRecipe()
