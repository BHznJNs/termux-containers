import os
from pathlib import Path
import shlex
import shutil
import subprocess

from .installation import record_shell
from .runtime import ProotDistro, RuntimeError_
from .state import state_root


DEFAULT_CONFIG = """# 相对绑定路径以本配置文件所在目录为基准。
# 取消注释并调整镜像、端口后执行 termux-containers apply。
services: {}
#  web:
#    image: nginxinc/nginx-unprivileged:stable-alpine
#    enabled: true
#    environment:
#      PORT: "8080"
#    volumes:
#      - ./data/web:/usr/share/nginx/html
"""


def require_termux():
    prefix = os.environ.get("PREFIX", "")
    if not (os.environ.get("TERMUX_VERSION") or "/com.termux/" in prefix) or not shutil.which("pkg"):
        raise RuntimeError_("init/安装脚本必须在 Android Termux 中运行")


def initialize(config_path, launcher):
    require_termux()
    home = Path.home()
    shell = Path(os.environ.get("SHELL", "bash")).name
    if shell not in ("bash", "zsh"):
        raise RuntimeError_(f"首版自启动仅支持 Bash/Zsh，当前 Shell: {shell}")
    missing = [pkg for pkg, executable in (("proot", "proot"), ("proot-distro", "proot-distro"))
               if not shutil.which(executable)]
    if missing:
        subprocess.run(["pkg", "install", "-y", *missing], check=True)
    runtime = ProotDistro()
    runtime.verify()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with config_path.open("x", encoding="utf-8") as handle:
            handle.write(DEFAULT_CONFIG)
    except FileExistsError:
        pass
    log_dir = state_root()
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = log_dir / "autostart.log"
    command = (f"{shlex.quote(str(launcher))} -f {shlex.quote(str(config_path))} start"
               f" >> {shlex.quote(str(log))} 2>&1 < /dev/null")
    # A configuration-specific marker allows multiple explicit init -f projects.
    import hashlib
    marker = hashlib.sha256(str(config_path).encode()).hexdigest()[:16]
    start = f"# >>> termux-containers {marker} >>>"
    end = f"# <<< termux-containers {marker} <<<"
    block = f"{start}\ncase $- in\n  *i*) ( {command} ) & ;;\nesac\n{end}\n"
    rc = home / ".bashrc" if shell == "bash" else Path(os.environ.get("ZDOTDIR", str(home))) / ".zshrc"
    try:
        record_shell(rc, marker)
    except ValueError as exc:
        raise RuntimeError_(f"无法记录安装信息: {exc}") from exc
    _update_block(rc, start, end, block)
    if shell == "bash":
        profile = next((home / name for name in (".bash_profile", ".bash_login", ".profile")
                        if (home / name).exists()), home / ".bash_profile")
        # Login shells do not necessarily source .bashrc. Trigger the same idempotent command.
        try:
            record_shell(profile, marker)
        except ValueError as exc:
            raise RuntimeError_(f"无法记录安装信息: {exc}") from exc
        _update_block(profile, start, end, block)
    print(f"初始化完成，配置: {config_path}")
    print(f"Session 自启动已写入 {rc}；日志: {log}")


def _update_block(path, start, end, block):
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""
    if start in content:
        left, rest = content.split(start, 1)
        if end not in rest:
            raise RuntimeError_(f"启动配置标记不完整，拒绝覆盖: {path}")
        _, right = rest.split(end, 1)
        content = left + block + right.lstrip('\n')
    else:
        content += ("\n" if content and not content.endswith('\n') else "") + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
