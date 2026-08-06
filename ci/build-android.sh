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
set -euo pipefail

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
    [ -d "$(dirname "$t")" ] && cp patches/HIDDeviceUSB.java "$t" && echo "    HIDDeviceUSB -> $t"
  done

  # Service loader
  for t in \
    "${P4A_DIR}/pythonforandroid/bootstraps/common/build/src/main/java/org/kivy/android/PythonService.java" \
    "${BUILD_DIR}/bootstrap_builds/sdl2/src/main/java/org/kivy/android/PythonService.java" \
    "${DIST_DIR}/src/main/java/org/kivy/android/PythonService.java"; do
    [ -d "$(dirname "$t")" ] && cp patches/PythonService.java "$t" && echo "    PythonService -> $t"
  done

  # Python activity
  for t in \
    "${P4A_DIR}/pythonforandroid/bootstraps/sdl2/build/src/main/java/org/kivy/android/PythonActivity.java" \
    "${BUILD_DIR}/bootstrap_builds/sdl2/src/main/java/org/kivy/android/PythonActivity.java" \
    "${DIST_DIR}/src/main/java/org/kivy/android/PythonActivity.java"; do
    [ -d "$(dirname "$t")" ] && cp patches/PythonActivity.java "$t" && echo "    PythonActivity -> $t"
  done

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
    cp "$FILTERLIB" LXST/ && echo "    filterlib.so injected"
  fi
}

# ----------------------------------------------------------------- 4. build
final_build() {
  echo "==> final build ($BUILD_TYPE)"
  if ! run_buildozer final; then
    show_real_error "$LOGDIR/buildozer-final.log"
    exit 1
  fi
}

vendor
prebake
patch_dist
final_build

echo "==> artifacts:"
ls -lh bin/*.apk 2>/dev/null || { echo "no APK produced"; exit 1; }
