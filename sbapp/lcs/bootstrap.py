# Liberty Chat Pro — first-run bootstrap
# Installs bundled service plugins and points Sideband at them.

import os, shutil
import RNS

BUNDLED_PLUGINS = ["ATAK-Plugin.py"]


def install_bundled_plugins(sideband):
    """Copy plugins shipped in assets/plugins into the app's writable plugin
    directory and set command_plugins_path, unless the user has already
    chosen their own plugin directory."""
    try:
        target = sideband.config.get("command_plugins_path")

        if target is None:
            target = os.path.join(sideband.app_dir, "plugins")
            sideband.config["command_plugins_path"] = target
            sideband.save_configuration()

        if not os.path.isdir(target):
            os.makedirs(target, exist_ok=True)

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source_dir = os.path.join(here, "assets", "plugins")

        for name in BUNDLED_PLUGINS:
            src = os.path.join(source_dir, name)
            dst = os.path.join(target, name)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.copyfile(src, dst)
                RNS.log("Installed bundled plugin: "+name, RNS.LOG_NOTICE)

    except Exception as e:
        RNS.log("Could not install bundled plugins: "+str(e), RNS.LOG_ERROR)
