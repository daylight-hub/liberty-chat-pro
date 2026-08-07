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
        # Newer p4a calls install_hostpython_prerequisites() -> self._host_recipe.pip
        # when building meson-based recipes (numpy 2.x).
        #
        # Rather than locating the pip3 script (whose location depends on
        # whether ensurepip did a system or user install), run pip as a module
        # through the hostpython binary. This always works regardless of where
        # pip's package landed, since the hostpython knows its own sys.path.
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
            # Get the hostpython's own lib directory so pip lands where
            # `python3 -m pip` can find it, rather than in a user-install
            # directory like /tmp/.local/ that vanishes between steps.
            hp_build = join(self.get_build_dir("arm64-v8a"), "native-build")
            hp_lib = join(hp_build, "lib", "python3.11", "site-packages")
            ensure_dir(hp_lib)

            print("RUNNING ENSUREPIP -> " + hp_lib)
            # PYTHONUSERBASE pointed at the native-build dir forces user
            # installs there. PYTHONPATH ensures the installed pip package
            # is immediately importable for subsequent pip calls.
            ep_env = {
                "HOME": hp_build,
                "PYTHONUSERBASE": hp_build,
                "PYTHONPATH": hp_lib,
                "PATH": os.environ.get("PATH", ""),
            }
            shprint(
                sh.Command(self.python_exe), "-m", "ensurepip", "-U",
                _env=ep_env
            )
            # Now install pip properly into the hostpython's own site-packages
            # so `python3 -m pip` works regardless of HOME or user-site.
            shprint(
                sh.Command(self.python_exe), "-m", "pip", "install",
                "--target", hp_lib, "--upgrade", "pip", "setuptools",
                _env=ep_env
            )
            print("RAN ENSUREPIP + pip bootstrap")

            # Write a sitecustomize.py so the hostpython always finds pip
            # when p4a invokes it as `python3 -m pip ...`, regardless of
            # what HOME or PYTHONPATH the caller sets.
            hp_stdlib = join(hp_build, "lib", "python3.11")
            sc_path = join(hp_stdlib, "sitecustomize.py")
            if not os.path.exists(sc_path):
                ensure_dir(hp_stdlib)
                with open(sc_path, "w") as f:
                    f.write(
                        "# Auto-generated by hostpython3 recipe\n"
                        "import sys, os\n"
                        "sp = os.path.join(os.path.dirname(__file__), 'site-packages')\n"
                        "if sp not in sys.path:\n"
                        "    sys.path.insert(0, sp)\n"
                    )
                print("Wrote sitecustomize.py -> " + sc_path)

            self.fix_pip_shebangs()


recipe = HostPython3Recipe()