from pythonforandroid.recipe import Recipe
from pythonforandroid.toolchain import current_directory, shprint
import sh
import os


class OpusFileRecipe(Recipe):
    version = "0.12"
    url = "https://downloads.xiph.org/releases/opus/opusfile-{version}.tar.gz"
    depends = ['libogg', 'libopus']
    built_libraries = {'libopusfile.so': '.libs'}

    def build_arch(self, arch):
        with current_directory(self.get_build_dir(arch.arch)):
            env = self.get_recipe_env(arch)
            flags = [
                "--host=" + arch.command_prefix,
                "--disable-http",
                "--disable-examples",
                "--disable-doc",
                "--disable-largefile",
            ]

            # opusfile's configure locates ogg and opus via pkg-config, but the
            # cross-compiled .pc files are not on PKG_CONFIG_PATH, so the lookup
            # fails ("Package 'ogg'/'opus' not found"). configure itself notes
            # that DEPS_CFLAGS / DEPS_LIBS can be set to bypass pkg-config, which
            # is what we do here, pointing at both dependency build trees.
            ogg_dir = self.get_recipe('libogg', self.ctx).get_build_dir(arch.arch)
            opus_dir = self.get_recipe('libopus', self.ctx).get_build_dir(arch.arch)

            # opus installs its public headers under include/opus/, but
            # opusfile includes them unprefixed (e.g. <opus_multistream.h>), so
            # expose both the base and the opus/ subdir. ogg headers are also
            # generated into the build tree, so include that copy as well.
            deps_cflags = (f"-I{ogg_dir}/include "
                           f"-I{opus_dir}/include -I{opus_dir}/include/opus")
            deps_libs = (f"-L{ogg_dir}/src/.libs -logg "
                         f"-L{opus_dir}/.libs -lopus")

            env["DEPS_CFLAGS"] = deps_cflags
            env["DEPS_LIBS"] = deps_libs
            # Keep the include path on CPPFLAGS too, for the compile stage.
            env["CPPFLAGS"] = env.get("CPPFLAGS", "") + " " + deps_cflags

            configure = sh.Command('./configure')
            shprint(configure, *flags, _env=env)
            shprint(sh.make, _env=env)


recipe = OpusFileRecipe()
