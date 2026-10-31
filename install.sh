#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [ -z "${TERMUX_VERSION:-}" ] && [[ "${PREFIX:-}" != */com.termux/* ]]; then
    printf '%s\n' '安装脚本必须在 Android Termux 中运行。' >&2
    exit 1
fi
if ! command -v pkg >/dev/null 2>&1; then
    printf '%s\n' '未找到 Termux pkg。' >&2
    exit 1
fi
pkg install -y python proot proot-distro
if [ ! -x "$ROOT/.venv/bin/python" ]; then
    python -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
chmod +x "$ROOT/termux-containers"
"$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from termux_containers.installation import install_command
try:
    install_command()
except (OSError, UnicodeError, ValueError) as exc:
    print(f"安装命令入口失败: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
"$ROOT/termux-containers" init "$@"
printf '%s\n' '安装完成。编辑 containers.yaml，然后运行 termux-containers apply。'
