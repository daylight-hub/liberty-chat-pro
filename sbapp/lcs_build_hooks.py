"""
Liberty Chat Pro — p4a build hooks.

Wire up in buildozer.spec:   p4a.hook = lcs_build_hooks.py

EXECUTION ORDER in p4a toolchain.py:
  self.hook("before_apk_build")
  build.parse_args_and_make_package()   <- applies src/patches/ to Java files
  self.hook("after_apk_build")          <- OUR JAVA PATCHING GOES HERE
  shprint(sh.Command("gradlew"), ...)   <- Gradle compiles
"""
import shutil
import os
import subprocess


def _patches_dir():
    hook_file = os.path.abspath(__file__)
    return os.path.join(os.path.dirname(hook_file), "patches")


def _java_dir():
    return os.path.join(
        os.getcwd(), "src", "main", "java", "org", "kivy", "android"
    )


def before_apk_build(toolchain):
    """Copy XML resources and clear src/patches that would overwrite our Java fixes."""
    dist_dir = os.getcwd()
    patches_dir = _patches_dir()

    # Ensure device_filter.xml and file_paths.xml are in res/xml.
    xml_dir = os.path.join(dist_dir, "src", "main", "res", "xml")
    os.makedirs(xml_dir, exist_ok=True)
    for xml_file in ("device_filter.xml", "file_paths.xml"):
        src = os.path.join(patches_dir, xml_file)
        dst = os.path.join(xml_dir, xml_file)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"[lcs_hook] before_apk_build: placed {xml_file}")

    # Remove any patches in src/patches/ that touch PythonService.java or
    # PythonActivity.java. build.py applies these AFTER our before_apk_build
    # hook, overwriting our Java fixes. Clearing them prevents that reversal.
    src_patches_dir = os.path.join(dist_dir, "src", "patches")
    if os.path.isdir(src_patches_dir):
        for fname in os.listdir(src_patches_dir):
            fpath = os.path.join(src_patches_dir, fname)
            try:
                content = open(fpath, errors='replace').read()
                if "PythonService" in content or "PythonActivity" in content:
                    os.remove(fpath)
                    print(f"[lcs_hook] before_apk_build: removed Java patch {fname}")
            except Exception as e:
                print(f"[lcs_hook] before_apk_build: could not inspect {fname}: {e}")

    print("[lcs_hook] before_apk_build: done")


def after_apk_build(toolchain):
    """Apply Java patches AFTER build.py has run src/patches/.

    This is the correct hook for Java file patching. build.parse_args_and_make_package()
    applies patches from src/patches/ which would overwrite a before_apk_build patch.
    after_apk_build fires after those patches, before gradlew compiles.
    """
    patches_dir = _patches_dir()
    java_dir = _java_dir()

    if not os.path.isdir(java_dir):
        print(f"[lcs_hook] after_apk_build: java_dir not found: {java_dir}")
        return

    print("[lcs_hook] after_apk_build: applying Java patches")
    for fname in ("PythonService.java", "PythonActivity.java"):
        src = os.path.join(patches_dir, fname)
        dst = os.path.join(java_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"[lcs_hook]   patched: {fname}")
        else:
            print(f"[lcs_hook]   skip {fname} (not in patches/)")

    # Run gradlew clean to ensure there are no stale .class files.
    try:
        print("[lcs_hook] after_apk_build: running gradlew clean")
        result = subprocess.run(
            ["./gradlew", "clean"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print("[lcs_hook] after_apk_build: gradlew clean OK")
        else:
            print(f"[lcs_hook] after_apk_build: gradlew clean failed: {result.stderr[-200:]}")
    except Exception as e:
        print(f"[lcs_hook] after_apk_build: gradlew clean error: {e}")

    print("[lcs_hook] after_apk_build: done")
