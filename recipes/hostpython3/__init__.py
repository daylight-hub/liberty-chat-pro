import sh
import os

from multiprocessing import cpu_count
from pathlib import Path
from os.path import join

from packaging.version import Version
from pythonforandroid.logger import shprint
from pythonforandroid.recipe import Recipe
from pythonforandroid.util import (
    BuildInterruptingException,
    current_directory,
    ensure_dir,
)
from pythonforandroid.prerequisites import OpenSSLPrerequisite

HOSTPYTHON_VERSION_UNSET_MESSAGE = (
    'The hostpython recipe must have set version'
)

SETUP_DIST_NOT_FIND_MESSAGE = (
    'Could not find Setup.dist or Setup in Python build'
)


class HostPython3Recipe(Recipe):
    '''
    The hostpython3's recipe.

    .. versionchanged:: 2019.10.06.post0
        Refactored from deleted class ``python.HostPythonRecipe`` into here.

    .. versionchanged:: 0.6.0
        Refactored into  the new class
        :class:`~pythonforandroid.python.HostPythonRecipe`
    '''

    version = '3.11.5'
    name = 'hostpython3'

    build_subdir = 'native-build'
    '''Specify the sub build directory for the hostpython3 recipe. Defaults
    to ``native-build``.'''

    url = 'https://www.python.org/ftp/python/{version}/Python-{version}.tgz'
    '''The default url to download our host python recipe. This url will
    change depending on the python version set in attribute :attr:`version`.'''

    patches = ['patches/pyconfig_detection.patch']

    @property
    def _exe_name(self):
        '''
        Returns the name of the python executable depending on the version.
        '''
        if not self.version:
            raise BuildInterruptingException(HOSTPYTHON_VERSION_UNSET_MESSAGE)
        return f'python{self.version.split(".")[0]}'

    @property
    def python_exe(self):
        '''Returns the full path of the hostpython executable.'''
        return join(self.get_path_to_python(), self._exe_name)

    def get_recipe_env(self, arch=None):
        env = os.environ.copy()
        openssl_prereq = OpenSSLPrerequisite()
        if env.get("PKG_CONFIG_PATH", ""):
            env["PKG_CONFIG_PATH"] = os.pathsep.join(
                [openssl_prereq.pkg_config_location, env["PKG_CONFIG_PATH"]]
            )
        else:
            env["PKG_CONFIG_PATH"] = openssl_prereq.pkg_config_location
        return env

    def should_build(self, arch):
        if Path(self.python_exe).exists():
            # no need to build, but we must set hostpython for our Context
            self.ctx.hostpython = self.python_exe
            return False
        return True

    def get_build_container_dir(self, arch=None):
        choices = self.check_recipe_choices()
        dir_name = '-'.join([self.name] + choices)
        return join(self.ctx.build_dir, 'other_builds', dir_name, 'desktop')

    def get_build_dir(self, arch=None):
        '''
        .. note:: Unlike other recipes, the hostpython build dir doesn't
            depend on the target arch
        '''
        return join(self.get_build_container_dir(), self.name)

    def get_path_to_python(self):
        return join(self.get_build_dir(), self.build_subdir)

    @property
    def site_root(self):
        return join(self.get_path_to_python(), "root")

    @property
    def site_bin(self):
        return join(self.site_root, self.site_dir, "bin")

    @property
    def local_dir(self):
        return join(self.site_root, "usr/local/")

    @property
    def local_bin(self):
        return join(self.site_root, "usr/local/bin/")

    @property
    def _pip(self):
        # Path to the pip3 script, if needed for shebang fixing.
        # With -m pip as the primary interface, this is secondary.
        for candidate in [
            join(self.get_path_to_python(), "bin", "pip3"),
            join(self.local_bin, "pip3"),
        ]:
            if os.path.isfile(candidate):
                return candidate
        return join(self.get_path_to_python(), "bin", "pip3")

    @property
    def pip(self):
        # pip is installed into /usr/local/lib/python3.11/site-packages/,
        # which is on the hostpython's compiled-in sys.path, so a simple
        # `python3 -m pip` always finds it — no PYTHONPATH tricks needed.
        return sh.Command(self.python_exe).bake("-m", "pip")

    def fix_pip_shebangs(self):
        # ensurepip writes shebangs pointing at the interpreter used to run it,
        # which may not be the final hostpython path. Rewrite them so the pip
        # scripts remain executable after the build moves things around.
        # Check both native-build/bin/ and the legacy --root location.
        dirs_to_check = [
            join(self.get_path_to_python(), "bin"),
            self.local_bin,
        ]
        for check_dir in dirs_to_check:
            if not os.path.exists(check_dir):
                continue
            self._fix_shebangs_in(check_dir)

    def _fix_shebangs_in(self, directory):
        for filename in os.listdir(directory):
            if not filename.startswith("pip"):
                continue

            pip_path = os.path.join(directory, filename)
            if not os.path.isfile(pip_path):
                continue

            with open(pip_path, "rb") as file:
                file_lines = file.read().splitlines()

            if not file_lines:
                continue

            file_lines[0] = f"#!{self.python_exe}".encode()

            with open(pip_path, "wb") as file:
                file.write(b"\n".join(file_lines) + b"\n")

    @property
    def site_dir(self):
        p_version = Version(self.version)
        return join(
            self.site_root,
            f"usr/local/lib/python{p_version.major}.{p_version.minor}/site-packages/"
        )

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)

        recipe_build_dir = self.get_build_dir(arch.arch)

        # Create a subdirectory to actually perform the build
        build_dir = join(recipe_build_dir, self.build_subdir)
        ensure_dir(build_dir)

        # Configure the build
        build_configured = False
        with current_directory(build_dir):
            if not Path('config.status').exists():
                shprint(sh.Command(join(recipe_build_dir, 'configure')), _env=env)
                build_configured = True

        with current_directory(recipe_build_dir):
            # Create the Setup file. This copying from Setup.dist is
            # the normal and expected procedure before Python 3.8, but
            # after this the file with default options is already named "Setup"
            setup_dist_location = join('Modules', 'Setup.dist')
            if Path(setup_dist_location).exists():
                shprint(sh.cp, setup_dist_location,
                        join(build_dir, 'Modules', 'Setup'))
            else:
                # Check the expected file does exist
                setup_location = join('Modules', 'Setup')
                if not Path(setup_location).exists():
                    raise BuildInterruptingException(
                        SETUP_DIST_NOT_FIND_MESSAGE
                    )

            shprint(sh.make, '-j', str(cpu_count()), '-C', build_dir, _env=env)

            # make a copy of the python executable giving it the name we want,
            # because we got different python's executable names depending on
            # the fs being case-insensitive (Mac OS X, Cygwin...) or
            # case-sensitive (linux)...so this way we will have an unique name
            # for our hostpython, regarding the used fs
            for exe_name in ['python.exe', 'python']:
                exe = join(self.get_path_to_python(), exe_name)
                if Path(exe).is_file():
                    shprint(sh.cp, exe, self.python_exe)
                    break

        ensure_dir(self.site_root)
        self.ctx.hostpython = self.python_exe
        if build_configured:
            # pip installation is handled by the build script's bootstrap_pip()
            # function which runs after prebake, using the hostpython binary
            # directly. This avoids permission errors (/usr/local is root-owned)
            # and p4a's should_build() skipping logic.
            pass


recipe = HostPython3Recipe()