#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [ -z "${TERMUX_VERSION:-}" ] && [[ "${PREFIX:-}" != */com.termux/* ]]; then
    printf '%s\n' '卸载脚本必须在 Android Termux 中运行。' >&2
    exit 1
fi
if [ -z "${PREFIX:-}" ] || [ ! -x "$PREFIX/bin/python" ]; then
    printf '%s\n' '未找到 Termux 系统 Python，请先执行 pkg install python。' >&2
    exit 1
fi
exec "$PREFIX/bin/python" "$ROOT/termux_containers/installation.py" "$@"
