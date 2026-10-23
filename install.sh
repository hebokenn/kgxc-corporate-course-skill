#!/bin/bash
# Installer bootstrap. Prepares Skill, media tools and local B2; never asks for API credentials.
set -euo pipefail
REPOSITORY="hebokenn/kgxc-corporate-course-skill"
VERSION="5.7.2"
UV_VERSION="0.11.21"
TASK_TMP=""
cleanup() { if [ -n "$TASK_TMP" ]; then rm -rf "$TASK_TMP"; fi; }
trap cleanup EXIT
INSTALL_SOURCE=""
if [ "${1:-}" = "--source" ]; then
  INSTALL_SOURCE="$2"; shift 2
elif [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/release.json" ]; then
  INSTALL_SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  if [ "$REPOSITORY" = "__REPOSITORY_PENDING__" ]; then
    echo "尚未绑定发布仓库 请使用完整下载目录内的 install.sh" >&2; exit 2
  fi
  TASK_TMP="$(mktemp -d)"
  curl --fail --location --retry 3 "https://codeload.github.com/${REPOSITORY}/tar.gz/refs/tags/v${VERSION}" -o "$TASK_TMP/source.tar.gz"
  mkdir "$TASK_TMP/source"
  tar -xzf "$TASK_TMP/source.tar.gz" -C "$TASK_TMP/source" --strip-components=1
  INSTALL_SOURCE="$TASK_TMP/source"
fi

INSTALL_PYTHON="$(command -v python3 || true)"
if [ -n "$INSTALL_PYTHON" ] && ! "$INSTALL_PYTHON" -c 'import sys;raise SystemExit(sys.version_info < (3,9))'; then INSTALL_PYTHON=""; fi
SKIP_RUNTIME=0
for ARG in "$@"; do case "$ARG" in --skill-only|--uninstall) SKIP_RUNTIME=1;; esac; done
UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ] && { [ "$SKIP_RUNTIME" = 0 ] || [ -z "$INSTALL_PYTHON" ]; }; then
  UV_LOCAL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kgxc-course/bootstrap/bin"
  TASK_UV_SCRIPT="$(mktemp)"
  curl --fail --location --retry 3 "https://astral.sh/uv/${UV_VERSION}/install.sh" -o "$TASK_UV_SCRIPT"
  UV_INSTALL_DIR="$UV_LOCAL_DIR" UV_NO_MODIFY_PATH=1 /bin/sh "$TASK_UV_SCRIPT"
  rm -f "$TASK_UV_SCRIPT"
  UV_BIN="$UV_LOCAL_DIR/uv"
fi
if [ -n "$INSTALL_PYTHON" ]; then
  if [ -n "$UV_BIN" ]; then "$INSTALL_PYTHON" "$INSTALL_SOURCE/scripts/install.py" --uv "$UV_BIN" "$@"
  else "$INSTALL_PYTHON" "$INSTALL_SOURCE/scripts/install.py" "$@"; fi
else
  UV_PYTHON_INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kgxc-course/runtime/python" "$UV_BIN" run --no-project --managed-python --python 3.12.13 python "$INSTALL_SOURCE/scripts/install.py" --uv "$UV_BIN" "$@"
fi
