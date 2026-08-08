from pythonforandroid.recipe import CythonRecipe, IncludedFilesBehaviour
from pythonforandroid.toolchain import current_directory, shprint
from os.path import join
import sh

# class PyCodec2Recipe(IncludedFilesBehaviour, CythonRecipe):
class PyCodec2Recipe(CythonRecipe):
    url = "https://github.com/markqvist/pycodec2/archive/438ee4f2f3ee30635a34caddf520cfaccdbbc646.zip"
    # src_filename = "../../../pycodec2"
    depends = ["setuptools", "numpy", "Cython", "codec2"]
    call_hostpython_via_targetpython = False

    def get_recipe_env(self, arch, with_flags_in_cc=True):
        """
        Adds codec2 recipe to include and library path.
        """
        env = super().get_recipe_env(arch, with_flags_in_cc)

        codec2_recipe = self.get_recipe('codec2', self.ctx)
        env['CFLAGS'] += codec2_recipe.include_flags(arch) +" -l:libcodec2.so"
        env['LDFLAGS'] += ' -L{}'.format(self.ctx.get_libs_dir(arch.arch))
        env['LDFLAGS'] += ' -L{}'.format(self.ctx.libs_dir)
        env['LDFLAGS'] += codec2_recipe.link_dirs_flags(arch)
        
        return env

    def install_hostpython_prerequisites(self, packages=None, force_upgrade=True):
        """Also install numpy into the hostpython for setup.py."""
        import subprocess, os
        python_exe = self.ctx.hostpython

        # Ensure numpy is importable in the hostpython before setup.py runs.
        r = subprocess.run([python_exe, "-c", "import numpy"], capture_output=True)
        if r.returncode != 0:
            # Get the hostpython prefix.
            r2 = subprocess.run(
                [python_exe, "-c", "import sys; print(sys.prefix)"],
                capture_output=True, text=True
            )
            prefix = r2.stdout.strip() if r2.returncode == 0 else os.path.dirname(python_exe)
            hp_site = os.path.join(prefix, "lib", "python3.11", "site-packages")
            os.makedirs(hp_site, exist_ok=True)
            print(f"[pycodec2] installing numpy into hostpython -> {hp_site}")
            subprocess.run(
                ["python3", "-m", "pip", "install", "--target", hp_site,
                 "--no-deps", "numpy==2.1.3", "-q"],
                check=True
            )
        super().install_hostpython_prerequisites(packages=packages, force_upgrade=force_upgrade)

    def build_arch(self, arch):
        super().build_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            pass
            # print(arch.arch)
            # print(arch)
            # shprint(sh.Command("pwd"))
            # shprint(sh.Command("ls"))
            
            # pe_args = ["--replace-needed", "libcodec2.so.1.2", "libcodec2.so", "build/lib.linux-x86_64-3.11/pycodec2/pycodec2.cpython-311-x86_64-linux-gnu.so"]
            # shprint(sh.Command("patchelf"), *pe_args)

            # pe_args = ["--replace-needed", "libcodec2.so.1.2", "libcodec2.so", f"../../../../python-installs/sideband/{arch.arch}/pycodec2/pycodec2.cpython-311-x86_64-linux-gnu.so"]
            # shprint(sh.Command("patchelf"), *pe_args)

            # ../../../../python-installs/sideband/armeabi-v7a/pycodec2/pycodec2.cpython-311-x86_64-linux-gnu.so
            # sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/pycodec2/armeabi-v7a__ndk_target_24/pycodec2/build/lib.linux-x86_64-3.11/pycodec2/pycodec2.cpython-311-x86_64-linux-gnu.so
            # sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/python-installs/sideband/armeabi-v7a/pycodec2/pycodec2.cpython-311-x86_64-linux-gnu.so
            # print("=========================")
            # input()


    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)

recipe = PyCodec2Recipe()

# patchelf --replace-needed libcodec2.so.1.2 libcodec2.so sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/sideband/_python_bundle__arm64-v8a/_python_bundle/site-packages/pycodec2/pycodec2.so
# patchelf --replace-needed libcodec2.so.1.2 libcodec2.so sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/sideband/_python_bundle__armeabi-v7a/_python_bundle/site-packages/pycodec2/pycodec2.so

# patchelf --replace-needed libcodec2.so.1.2 libcodec2.so sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/sideband/_python_bundle__arm64-v8a/_python_bundle/site-packages/pycodec2/pycodec2.so; patchelf --replace-needed libcodec2.so.1.2 libcodec2.so sbapp/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/sideband/_python_bundle__armeabi-v7a/_python_bundle/site-packages/pycodec2/pycodec2.so