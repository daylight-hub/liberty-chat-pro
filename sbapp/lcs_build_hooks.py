"""
Liberty Chat Pro — p4a build hooks.

Wire up in buildozer.spec:   p4a.hook = lcs_build_hooks.py
"""
import shutil, os, subprocess


def _patches_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "patches")


def before_apk_build(toolchain):
    """Place XML resources. Do NOT touch Java files here — build.py
    applies src/patches/ after this and would undo any Java changes."""
    dist_dir = os.getcwd()
    patches_dir = _patches_dir()
    xml_dir = os.path.join(dist_dir, "src", "main", "res", "xml")
    os.makedirs(xml_dir, exist_ok=True)
    for f in ("device_filter.xml", "file_paths.xml"):
        src = os.path.join(patches_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(xml_dir, f))
            print(f"[lcs_hook] placed {f}")
    print("[lcs_hook] before_apk_build done")


def after_apk_build(toolchain):
    """Fix the notification channel ID in PythonService.java in-place.

    We do NOT replace PythonService.java or PythonActivity.java wholesale
    because Sideband's patched versions are incompatible with p4a
    v2026.05.09's SDL2 (sendCommand visibility, method overrides).

    The ONLY thing we need to fix is the notification channel string,
    which references the old package io.unsigned.sideband. We patch it
    with sed-style replacement directly in the stock file.

    The ServiceSidebandservice import in the original patches file is NOT
    needed — Android loads the service class via the manifest, not via
    a direct import in PythonService.java.
    """
    dist_dir = os.getcwd()
    java_dir = os.path.join(dist_dir, "src", "main", "java", "org", "kivy", "android")
    ps_path = os.path.join(java_dir, "PythonService.java")

    if not os.path.isfile(ps_path):
        print(f"[lcs_hook] PythonService.java not found at {ps_path}")
        return

    content = open(ps_path, encoding="utf-8").read()
    # Replace any stale package reference in string literals (notification
    # channel ID, broadcast intents, etc.) with our package name.
    fixed = content.replace(
        "io.unsigned.sideband",
        "network.lcs.libertychatpro"
    )
    if fixed != content:
        open(ps_path, "w", encoding="utf-8").write(fixed)
        print("[lcs_hook] PythonService.java: replaced io.unsigned.sideband references")
    else:
        print("[lcs_hook] PythonService.java: no stale references (already clean or stock)")

    # Clear Gradle build cache so changed files compile fresh.
    try:
        r = subprocess.run(["./gradlew", "clean"], capture_output=True,
                           text=True, timeout=120)
        print(f"[lcs_hook] gradlew clean: {'OK' if r.returncode == 0 else 'FAILED'}")
    except Exception as e:
        print(f"[lcs_hook] gradlew clean error (non-fatal): {e}")
    print("[lcs_hook] after_apk_build done")
