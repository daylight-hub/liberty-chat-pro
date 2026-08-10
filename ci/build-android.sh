#!/usr/bin/env bash
#
# Liberty Chat Pro — Android build pipeline for CI
#
# Sideband cannot be built with a plain `buildozer android debug`. Upstream's
# sbapp/Makefile runs a multi-stage process that depends on Mark Qvist's local
# filesystem layout (sibling Reticulum/LXMF/LXST checkouts and a private
# dist_archive). This script reproduces the parts that matter, from public
# sources only.
#
# Stages:
#   1. vendor  - copy RNS / LXMF / LXST packages into sbapp/ (upstream: `getrns`)
#   2. prebake - first buildozer pass, generates the p4a dist tree
#   3. patch   - overwrite SDL/service/activity Java + inject XML (upstream: `pacthfiles`)
#   4. build   - real build against the patched dist
#
# Explicit error handling: don't use set -e (it silently kills the script
# on compound commands and produces no traceable output in CI). Instead we
# use set -u for undefined vars and pipefail, and check exit codes explicitly.
set -uo pipefail

BUILD_TYPE="${1:-debug}"
ARCH="arm64-v8a"

cd "$(dirname "$0")/../sbapp"
SBAPP="$PWD"

# Dist name is derived from package.name in buildozer.spec.
DIST_NAME=$(grep -E '^package\.name' buildozer.spec | cut -d= -f2 | tr -d ' ')
echo "==> dist name: $DIST_NAME"

DIST_DIR=".buildozer/android/platform/build-${ARCH}/dists/${DIST_NAME}"
BUILD_DIR=".buildozer/android/platform/build-${ARCH}/build"
P4A_DIR=".buildozer/android/platform/python-for-android"

# ----------------------------------------------------------- 0. host tools
# codec2's CMakeLists invokes `generate_codebook` as a bare command name, so it
# must be on PATH built for the HOST arch. Mark's fork never builds it as a
# target - it assumes a system codec2 install provides it. On a clean runner it
# does not exist, so every codebook rule fails with exit 127 and libcodec2
# never links. Build it natively from the exact commit the recipe pins.
CODEC2_COMMIT="00e01c9d72d3b1607e165c71c4c9c942d277dfac"
HOSTTOOLS="$SBAPP/../.hosttools"

host_tools() {
  if [ -x "$HOSTTOOLS/generate_codebook" ]; then
    echo "==> host generate_codebook already built"
  else
    echo "==> building host generate_codebook (codec2 @ ${CODEC2_COMMIT:0:8})"
    mkdir -p "$HOSTTOOLS"
    local tmp; tmp=$(mktemp -d)
    curl -sL "https://github.com/markqvist/codec2/archive/${CODEC2_COMMIT}.tar.gz" \
      -o "$tmp/codec2.tar.gz"
    tar xzf "$tmp/codec2.tar.gz" -C "$tmp"
    cc -O2 -o "$HOSTTOOLS/generate_codebook" \
      "$tmp"/codec2-*/src/generate_codebook.c -lm
    rm -rf "$tmp"
  fi
  export PATH="$HOSTTOOLS:$PATH"
  command -v generate_codebook >/dev/null || { echo "FATAL: generate_codebook not on PATH"; exit 1; }
  echo "    generate_codebook: $(command -v generate_codebook)"
}

# ---------------------------------------------------------------- 1. vendor
# Upstream copies these from sibling git checkouts. We take them from the
# versions setup.py requires, so the vendored source matches what the app
# expects at runtime.
vendor() {
  echo "==> vendoring RNS / LXMF / LXST"
  rm -rf RNS LXMF LXST
  local tmp; tmp=$(mktemp -d)

  python -m pip download --no-deps --no-binary :all: \
    "rns>=1.2.0" "lxmf>=0.9.6" "lxst>=0.4.6" -d "$tmp" \
    || python -m pip download --no-deps "rns>=1.2.0" "lxmf>=0.9.6" "lxst>=0.4.6" -d "$tmp"

  ( cd "$tmp"
    for f in *.tar.gz; do [ -e "$f" ] && tar xzf "$f"; done
    for f in *.whl;    do [ -e "$f" ] && unzip -qo "$f" -d "${f%.whl}"; done
  )

  for pkg in RNS LXMF LXST; do
    local src
    src=$(find "$tmp" -maxdepth 3 -type d -name "$pkg" | head -1)
    if [ -z "$src" ]; then echo "FATAL: could not locate $pkg"; exit 1; fi
    cp -r "$src" "./$pkg"
    rm -rf "./$pkg/__pycache__" "./$pkg/Utilities/$pkg"
    echo "    $pkg <- $src"
  done
  rm -rf "$tmp"
}

LOGDIR="$SBAPP/../build-logs"
mkdir -p "$LOGDIR"

# buildozer's own tail is famously unhelpful ("the error might be hidden in the
# log above"). This pulls the actual failure out of the captured output.
show_real_error() {
  local log="$1"
  echo ""
  echo "################ EXTRACTED ERROR CONTEXT ################"
  # Compiler / recipe / python failures, with surrounding lines
  grep -n -E "error:|Error:|ERROR|fatal error|Traceback|Exception|No such file|not found|undefined reference|command failed|Aborted" "$log" \
    | grep -v -E "The error might be hidden|might be hidden in the log" \
    | tail -40 || true
  echo ""
  echo "################ LAST 150 LINES ################"
  tail -150 "$log"
  echo "########################################################"
}

run_buildozer() {
  local phase="$1"; shift
  local log="$LOGDIR/buildozer-${phase}.log"
  echo "==> buildozer $BUILD_TYPE  [phase: $phase]  -> $log"
  set +e
  buildozer -v android "$BUILD_TYPE" 2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  set -e
  return $rc
}

# --------------------------------------------------------------- 2. prebake
# The first pass generates the dist tree that stage 3 patches. It is expected
# to be slow, and upstream tolerates it failing - the tree is what matters.
prebake() {
  if [ -f "${DIST_DIR}/src/main/res/xml/device_filter.xml" ]; then
    echo "==> dist already prepared, skipping prebake"
    return 0
  fi
  echo "==> prebake pass (generating dist tree)"
  if ! run_buildozer prebake; then
    echo "    prebake returned non-zero"
    if [ ! -d "$DIST_DIR" ]; then
      echo "    and produced no dist tree - this is a hard failure"
      show_real_error "$LOGDIR/buildozer-prebake.log"
      exit 1
    fi
    echo "    but dist tree exists, continuing"
  fi
}

# ----------------------------------------------------------------- 3. patch
patch_p4a_templates() {
  # p4a apk copies Java files from its own bootstrap/common/build/ templates
  # into dists/, overwriting anything we put in patch_dist(). Patch the
  # p4a templates BEFORE final_build so our version is what p4a copies.
  local P4A="$SBAPP/.buildozer/android/platform/python-for-android"
  local COMMON="$P4A/pythonforandroid/bootstraps/common/build/src/main/java/org/kivy/android"
  local SDL2="$P4A/pythonforandroid/bootstraps/sdl2/build/src/main/java/org/kivy/android"

  for target_dir in "$COMMON" "$SDL2"; do
    if [ -d "$target_dir" ]; then
      cp patches/PythonService.java  "$target_dir/PythonService.java"  && echo "    PythonService.java -> $target_dir"
      [ -f patches/PythonActivity.java ] && cp patches/PythonActivity.java "$target_dir/PythonActivity.java" && echo "    PythonActivity.java -> $target_dir"
    fi
  done
  echo "==> p4a templates patched"
}

patch_dist() {
  echo "==> patching dist"
  if [ ! -d "$DIST_DIR" ]; then
    echo "FATAL: dist dir missing: $DIST_DIR"
    ls -la "$(dirname "$DIST_DIR")" 2>/dev/null || true
    exit 1
  fi

  # USB HID behaviour
  for t in \
    "${BUILD_DIR}/bootstrap_builds/sdl2/jni/SDL/android-project/app/src/main/java/org/libsdl/app/HIDDeviceUSB.java" \
    "${DIST_DIR}/src/main/java/org/libsdl/app/HIDDeviceUSB.java" \
    "${DIST_DIR}/jni/SDL/android-project/app/src/main/java/org/libsdl/app/HIDDeviceUSB.java"; do
    [ -d "$(dirname "$t")" ] && { cp patches/HIDDeviceUSB.java "$t" && echo "    HIDDeviceUSB -> $t"; } || true
  done

  # Service loader
  for t in \
    "${P4A_DIR}/pythonforandroid/bootstraps/common/build/src/main/java/org/kivy/android/PythonService.java" \
    "${BUILD_DIR}/bootstrap_builds/sdl2/src/main/java/org/kivy/android/PythonService.java" \
    "${DIST_DIR}/src/main/java/org/kivy/android/PythonService.java"; do
    [ -d "$(dirname "$t")" ] && { cp patches/PythonService.java "$t" && echo "    PythonService -> $t"; } || true
  done

  # Python activity (skip if our patched version is absent — stock p4a file is fine)
  if [ -f patches/PythonActivity.java ]; then
    for t in \
      "${P4A_DIR}/pythonforandroid/bootstraps/sdl2/build/src/main/java/org/kivy/android/PythonActivity.java" \
      "${BUILD_DIR}/bootstrap_builds/sdl2/src/main/java/org/kivy/android/PythonActivity.java" \
      "${DIST_DIR}/src/main/java/org/kivy/android/PythonActivity.java"; do
      [ -d "$(dirname "$t")" ] && { cp patches/PythonActivity.java "$t" && echo "    PythonActivity -> $t"; } || true
    done
  else
    echo "    PythonActivity.java not in patches/ — using stock p4a version"
  fi

  # XML + build.py injection
  mkdir -p "${DIST_DIR}/src/main/res/xml" "${DIST_DIR}/templates"
  cp patches/device_filter.xml        "${DIST_DIR}/src/main/res/xml/"
  cp patches/file_paths.xml           "${DIST_DIR}/src/main/res/xml/"
  cp patches/AndroidManifest.tmpl.xml "${DIST_DIR}/templates/"
  cp patches/p4a_build.py             "${DIST_DIR}/build.py"
  echo "    xml + build.py injected"

  # pycodec2 links against a versioned soname Android will not load
  local PC2="${DIST_DIR}/_python_bundle__${ARCH}/_python_bundle/site-packages/pycodec2/pycodec2.so"
  if [ -f "$PC2" ]; then
    patchelf --replace-needed libcodec2.so.1.2 libcodec2.so "$PC2" && echo "    pycodec2 soname patched"
  else
    echo "    pycodec2.so not present yet (will be handled on rebuild)"
  fi

  # LXST native filter lib must be copied back out for packaging
  local FILTERLIB="${DIST_DIR}/_python_bundle__${ARCH}/_python_bundle/site-packages/LXST/filterlib.so"
  if [ -f "$FILTERLIB" ]; then
    { cp "$FILTERLIB" LXST/ && echo "    filterlib.so injected"; } || echo "    filterlib.so copy failed (non-fatal)"
  fi
}

# ----------------------------------------------------------------- 4. build
final_build() {
  echo "==> final build ($BUILD_TYPE)"

  # p4a apk may regenerate dist files before Gradle compiles.
  # Re-apply the Java patches right before build so the compiled files
  # are definitely ours, even if p4a re-created the dist.
  local JAVA_DIR="$SBAPP/.buildozer/android/platform/build-${ARCH}/dists/${DIST_NAME}/src/main/java/org/kivy/android"
  if [ -d "$JAVA_DIR" ]; then
    echo "==> re-applying Java patches before Gradle (belt-and-suspenders)"
    cp "$SBAPP/patches/PythonService.java"  "$JAVA_DIR/PythonService.java"        && echo "    PythonService.java applied" || echo "    PythonService.java copy failed (non-fatal)"
    if [ -f "$SBAPP/patches/PythonActivity.java" ]; then
      cp "$SBAPP/patches/PythonActivity.java" "$JAVA_DIR/PythonActivity.java"         && echo "    PythonActivity.java applied" || echo "    PythonActivity.java copy failed (non-fatal)"
    fi
  fi

  if ! run_buildozer final; then
    show_real_error "$LOGDIR/buildozer-final.log"
    exit 1
  fi
}

# Force-clean recipes whose build logic changed, with explicit verification.
# This runs INSIDE the script (not as a separate CI step) so there is no
# ambiguity about step ordering or working directory relative to the cache
# restore - it executes immediately before buildozer, in the same shell,
# against the same paths buildozer itself will use.
clean_stale_recipes() {
  echo "==> checking for stale recipe builds to clean"
  local other_builds=".buildozer/android/platform/build-arm64-v8a/build/other_builds"
  for name in hostpython3 "python3*" numpy cryptography; do
    for d in $other_builds/$name; do
      if [ -e "$d" ]; then
        echo "    removing: $d"
        rm -rf "$d"
      else
        echo "    not present (already clean): $d"
      fi
    done
  done

  # Also remove cryptography from EVERY cached location — recipe build,
  # installed site-packages, AND the packaged _python_bundle inside the dist.
  # The dist's bundle is a tar that bakes in compiled .so files; if it
  # survives, the old Rust abi3.so ends up on the device regardless of
  # whether the recipe was rebuilt.
  local py_installs="$SBAPP/.buildozer/android/platform/build-arm64-v8a/build/python-installs"
  for inst_dir in "$py_installs"/*/arm64-v8a/cryptography; do
    if [ -e "$inst_dir" ]; then
      echo "    removing installed: $inst_dir"
      rm -rf "$inst_dir"
    fi
  done

  # Remove ONLY the cryptography directory inside the dist's _python_bundle,
  # not the whole bundle (build.py needs the directory to exist for make_tar).
  for bundle_dir in     "$SBAPP/.buildozer/android/platform/build-arm64-v8a/dists/${DIST_NAME}/_python_bundle__arm64-v8a/_python_bundle/site-packages/cryptography"     "$SBAPP/.buildozer/android/platform/build-arm64-v8a/dists/${DIST_NAME}/_python_bundle/site-packages/cryptography"; do
    if [ -e "$bundle_dir" ]; then
      echo "    removing bundled cryptography: $bundle_dir"
      rm -rf "$bundle_dir"
    fi
  done
  # Also kill any stray _rust.abi3.so anywhere in the dist
  find "$SBAPP/.buildozer/android/platform/build-arm64-v8a/dists/${DIST_NAME}"     -name "_rust.abi3.so" -delete -print 2>/dev/null | while read f; do
    echo "    deleted stale: $f"
  done
  # Verify: prove the directories are actually gone before continuing.
  if [ -d "$other_builds/hostpython3" ]; then
    echo "FATAL: $other_builds/hostpython3 still exists after cleanup"
    ls -la "$other_builds/hostpython3" || true
    exit 1
  fi
  echo "==> stale recipe cleanup verified"
}

echo "==> [1/6] clean_stale_recipes"
clean_stale_recipes || { echo "FATAL: clean_stale_recipes failed (exit $?)"; exit 1; }

echo "==> [2/6] host_tools"
host_tools          || { echo "FATAL: host_tools failed (exit $?)"; exit 1; }

echo "==> [3/6] vendor"
vendor              || { echo "FATAL: vendor failed (exit $?)"; exit 1; }

echo "==> [4/6] prebake"
prebake             || { echo "FATAL: prebake failed (exit $?)"; exit 1; }
# -------------------------------------------------------- 3b. pip bootstrap
# The hostpython binary is built with --prefix=<build_dir>/native-build
# (Mark's recipe sets sys_prefix = build_dir/android-root, but the actual
# hostpython prefix is the native-build directory itself). We can't rely on
# the recipe's should_build() ever running our ensurepip code, so we do it
# here directly in the build script after prebake.
bootstrap_pip() {
  local HP_BIN
  HP_BIN=$(find "$SBAPP/.buildozer/android/platform/build-arm64-v8a/build/other_builds/hostpython3"     -name "python3" -type f 2>/dev/null | head -1)

  if [ -z "$HP_BIN" ]; then
    echo "==> WARNING: hostpython3 binary not found, skipping pip bootstrap"
    return 0
  fi
  echo "==> hostpython binary: $HP_BIN"

  # Check if pip is already importable.
  if "$HP_BIN" -c "import pip" 2>/dev/null; then
    echo "==> pip already importable in hostpython"
    return 0
  fi

  echo "==> bootstrapping pip into hostpython"

  # Ask the binary where it looks for site-packages.
  local HP_SITE
  HP_SITE=$("$HP_BIN" -c "
import site, sys
sp = site.getsitepackages()
print(sp[0] if sp else (sys.prefix + '/lib/python3.11/site-packages'))
" 2>/dev/null)

  if [ -z "$HP_SITE" ]; then
    # Fallback: derive from binary location (native-build/bin/python3 -> native-build/lib/...)
    local HP_NATBUILD; HP_NATBUILD=$(dirname "$(dirname "$HP_BIN")")
    HP_SITE="$HP_NATBUILD/lib/python3.11/site-packages"
  fi
  echo "==> target site-packages: $HP_SITE"
  mkdir -p "$HP_SITE"

  # Download pip/setuptools wheels using the runner's system Python, then
  # install them with --target into the hostpython's site-packages.
  # This works regardless of /usr/local ownership since we write to the
  # build tree, not the system prefix.
  local TMP; TMP=$(mktemp -d)
  echo "==> downloading pip + setuptools wheels"
  python3 -m pip download pip setuptools --no-deps -d "$TMP" -q 2>&1 | tail -3

  echo "==> installing into $HP_SITE"
  for whl in "$TMP"/*.whl; do
    python3 -m pip install --target "$HP_SITE" --no-deps "$whl" -q
  done
  rm -rf "$TMP"

  # Verify
  if "$HP_BIN" -c "import pip; print('pip', pip.__version__)" 2>/dev/null; then
    echo "==> pip bootstrap succeeded"
  else
    echo "==> FATAL: pip still not importable after bootstrap"
    echo "    HP_BIN=$HP_BIN"
    echo "    HP_SITE=$HP_SITE"
    "$HP_BIN" -c "import sys; print('sys.path:', sys.path)"
    exit 1
  fi
}

echo "==> [5/6] patch_dist"
patch_dist          || { echo "FATAL: patch_dist failed (exit $?)"; exit 1; }

echo "==> [5b] bootstrap_pip"
bootstrap_pip       || { echo "FATAL: bootstrap_pip failed (exit $?)"; exit 1; }

echo "==> [5c] patch_p4a_templates"
patch_p4a_templates || { echo "FATAL: patch_p4a_templates failed (exit $?)"; exit 1; }

echo "==> [6/6] final_build"
final_build         || { echo "FATAL: final_build failed (exit $?)"; exit 1; }

echo "==> artifacts:"
ls -lh bin/*.apk 2>/dev/null || { echo "no APK produced"; exit 1; }
