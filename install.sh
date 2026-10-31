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
TARGET="$PREFIX/bin/termux-containers"
SIGNATURE='# managed by termux-containers install.sh'
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
    if ! grep -Fqx -- "$SIGNATURE" "$TARGET"; then
        printf '拒绝覆盖已有命令: %s\n' "$TARGET" >&2
        exit 1
    fi
fi
# Python shlex.quote preserves repository paths containing shell metacharacters.
"$ROOT/.venv/bin/python" - "$TARGET" "$ROOT/termux-containers" <<'PY'
from pathlib import Path
import os
import shlex
import sys
path = Path(sys.argv[1])
script = '#!' + os.environ['PREFIX'] + '/bin/bash\n'
script += '# managed by termux-containers install.sh\n'
script += 'exec ' + shlex.quote(sys.argv[2]) + ' "$@"\n'
path.write_text(script, encoding='utf-8')
path.chmod(0o755)
PY
"$ROOT/termux-containers" init "$@"
printf '%s\n' '安装完成。编辑 containers.yaml，然后运行 termux-containers apply。'
