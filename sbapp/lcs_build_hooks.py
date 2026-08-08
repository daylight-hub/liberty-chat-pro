"""
Liberty Chat Pro — p4a build hooks.

p4a calls these functions at specific points in the build pipeline.
`before_apk_build` fires after prepare_build_dir() populates the Gradle
project (including copying bootstrap Java from p4a's own templates) and
before Gradle runs. This is the only hook that runs at the right moment
to overwrite p4a's stock PythonService.java with our patched version.

Wire up in buildozer.spec:   p4a.hook = lcs_build_hooks.py
"""
import shutil
import os
import sys


def before_apk_build(toolchain):
    """Overwrite bootstrap Java files with LCS-patched versions.

    p4a's prepare_build_dir() copies PythonService.java from its own
    bootstrap/common/build templates into the dist, undoing any patches
    we applied earlier. This hook runs immediately after prepare_build_dir
    and rewrites the correct files before Gradle compiles them.
    """
    # cwd is dist.dist_dir when the hook fires.
    dist_dir = os.getcwd()
    java_dir = os.path.join(
        dist_dir, "src", "main", "java", "org", "kivy", "android"
    )

    # Locate the patches directory — two levels up from the hook file.
    hook_file = os.path.abspath(__file__)
    sbapp_dir = os.path.dirname(hook_file)
    patches_dir = os.path.join(sbapp_dir, "patches")

    patches = {
        "PythonService.java": os.path.join(patches_dir, "PythonService.java"),
        "PythonActivity.java": os.path.join(patches_dir, "PythonActivity.java"),
    }

    print("[lcs_hook] before_apk_build: applying Java patches")
    for fname, src in patches.items():
        dst = os.path.join(java_dir, fname)
        if not os.path.isfile(src):
            print(f"[lcs_hook]   SKIP {fname} (source not found: {src})")
            continue
        if not os.path.isdir(java_dir):
            print(f"[lcs_hook]   SKIP {fname} (java_dir missing: {java_dir})")
            continue
        shutil.copy2(src, dst)
        print(f"[lcs_hook]   patched: {fname}")

    # Also ensure device_filter.xml and file_paths.xml are in place.
    xml_dir = os.path.join(dist_dir, "src", "main", "res", "xml")
    os.makedirs(xml_dir, exist_ok=True)
    for xml_file in ("device_filter.xml", "file_paths.xml"):
        src = os.path.join(patches_dir, xml_file)
        dst = os.path.join(xml_dir, xml_file)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"[lcs_hook]   patched: {xml_file}")

    print("[lcs_hook] before_apk_build: done")
