from pythonforandroid.recipe import Recipe, MesonRecipe
from os.path import join
import shutil

NUMPY_NDK_MESSAGE = (
    "In order to build numpy, you must set minimum ndk api (minapi) to `24`.\n"
)


class NumpyRecipe(MesonRecipe):

    def install_hostpython_prerequisites(self, packages=None, force_upgrade=True):
        """Override to bootstrap pip into the hostpython BEFORE using it.

        The local hostpython3 recipe is compiled without pip (it predates
        p4a's pip-in-hostpython design). Rather than call
        ``native-build/python3 -m pip`` (which fails: No module named pip),
        we:

        1. Find the hostpython's site-packages via site.getsitepackages().
        2. Use the runner's system pip to download wheels and install them
           into that directory with --target.
        3. Then call the normal prerequisite install using the now-working pip.
        """
        import subprocess
        import site as _site
        import os

        python_exe = self.ctx.hostpython

        # ---- 1. ensure pip is importable in the hostpython ----------------
        result = subprocess.run(
            [python_exe, "-c", "import pip"],
            capture_output=True
        )
        if result.returncode != 0:
            # Ask the hostpython where its site-packages are.
            # The hostpython is now compiled with --prefix=native-build so
            # site.getsitepackages() returns the writable build-tree path.
            # We create the directory (it won't exist before make install)
            # then install pip/setuptools into it via the system pip.
            r = subprocess.run(
                [python_exe, "-c",
                 "import sys; print(sys.prefix)"],
                capture_output=True, text=True
            )
            if r.returncode == 0 and r.stdout.strip():
                prefix = r.stdout.strip()
            else:
                # Fallback: prefix = directory containing the binary
                # (binary is at native-build/python3, so prefix = native-build)
                prefix = os.path.dirname(python_exe)

            # Python always uses lib/pythonX.Y/site-packages under prefix
            hp_site = os.path.join(prefix, "lib", "python3.11", "site-packages")
            print(f"[numpy] bootstrapping pip -> {hp_site}")
            os.makedirs(hp_site, exist_ok=True)

            # Use system pip to download and install pip+setuptools into hp_site
            tmp = "/tmp/pip_bootstrap_wheels"
            os.makedirs(tmp, exist_ok=True)
            subprocess.run(
                ["python3", "-m", "pip", "download",
                 "pip", "setuptools", "--no-deps", "-d", tmp, "-q"],
                check=True
            )
            for whl in os.listdir(tmp):
                if whl.endswith(".whl"):
                    subprocess.run(
                        ["python3", "-m", "pip", "install",
                         "--target", hp_site, "--no-deps",
                         os.path.join(tmp, whl), "-q"],
                        check=True
                    )

            # Verify
            result = subprocess.run(
                [python_exe, "-c", "import pip; print('pip', pip.__version__)"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"[numpy] pip bootstrap ok: {result.stdout.strip()}")
            else:
                raise RuntimeError(
                    f"pip bootstrap failed for {python_exe}\n"
                    f"hp_site={hp_site}\n"
                    f"stderr={result.stderr}"
                )

        # ---- 2. now run the normal prerequisite install --------------------
        super().install_hostpython_prerequisites(
            packages=packages, force_upgrade=force_upgrade
        )


    # Pinned to 2.1.3: numpy 2.2+ adds unique.cpp which uses std::unordered_map
    # in a way that NDK r25b's libc++ (LLVM 14) cannot compile:
    #   error: no template named 'unordered_map' in namespace 'std'
    # Sideband requires numpy>=2.0.0 (setup.py), so 2.1.3 satisfies it.
    # Upgrade when NDK is bumped past r25b.
    version = "v2.1.3"
    url = "git+https://github.com/numpy/numpy"
    extra_build_args = ["-Csetup-args=-Dblas=none", "-Csetup-args=-Dlapack=none"]
    need_stl_shared = True
    min_ndk_api_support = 24

    def get_include(self, arch):
        return join(
            self.ctx.get_python_install_dir(arch.arch), "numpy/_core/include",
        )

    def get_recipe_meson_options(self, arch):
        options = super().get_recipe_meson_options(arch)
        options["properties"]["longdouble_format"] = (
            "IEEE_DOUBLE_LE" if arch.arch in ["armeabi-v7a", "x86"] else "IEEE_QUAD_LE"
        )
        return options

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix
        env["NPY_DISABLE_SVML"] = "1"
        env["TARGET_PYTHON_EXE"] = join(
            Recipe.get_recipe("python3", self.ctx).get_build_dir(arch.arch),
            "android-build",
            "python",
        )
        return env

    def get_hostrecipe_env(self, arch=None):
        env = super().get_hostrecipe_env(arch=arch)
        env["RANLIB"] = shutil.which("ranlib")
        return env


recipe = NumpyRecipe()
