"""Installation bookkeeping and removal, using only the Python standard library."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / ".installation.json"
SIGNATURE = "# managed by termux-containers install.sh"
START = re.compile(r"^# >>> termux-containers ([0-9a-f]{16}) >>>$")


def load_record():
    try:
        data = json.loads(RECORD.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"root": str(ROOT), "command": None, "shells": []}
    if (not isinstance(data, dict) or data.get("root") != str(ROOT)
            or not isinstance(data.get("shells"), list)
            or (data.get("command") is not None and not isinstance(data["command"], str))):
        raise ValueError("安装记录损坏或属于另一仓库，拒绝操作")
    for entry in data["shells"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
                or not Path(entry["path"]).is_absolute()
                or not isinstance(entry.get("marker"), str)
                or not re.fullmatch(r"[0-9a-f]{16}", entry["marker"])):
            raise ValueError("Shell 安装记录损坏，拒绝操作")
    data.setdefault("command", None)
    return data


def save_record(data):
    fd, temporary = tempfile.mkstemp(dir=ROOT, prefix=".installation-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, RECORD)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def record_shell(path, marker):
    data = load_record()
    entry = {"path": str(path.absolute()), "marker": marker}
    if entry not in data["shells"]:
        data["shells"].append(entry)
    # Record intent before modifying the shell file, including partial init failures.
    save_record(data)


def wrapper_content():
    return (f"#!{os.environ['PREFIX']}/bin/bash\n{SIGNATURE}\n"
            f"exec {shlex.quote(str(ROOT / 'termux-containers'))} \"$@\"\n")


def install_command():
    target = Path(os.environ["PREFIX"]) / "bin/termux-containers"
    content = wrapper_content()
    if target.is_symlink():
        raise ValueError(f"拒绝覆盖符号链接命令入口: {target}")
    if target.exists() and target.read_text(encoding="utf-8") != content:
        raise ValueError(f"拒绝覆盖不属于本仓库或已被修改的命令入口: {target}")
    data = load_record()
    data["command"] = str(target)
    save_record(data)
    target.write_text(content, encoding="utf-8")
    target.chmod(0o755)


def clean_shell(content, recorded_markers):
    lines = content.splitlines(keepends=True)
    result = []
    index = 0
    owner = f"  *i*) ( {shlex.quote(str(ROOT / 'termux-containers'))} -f "
    while index < len(lines):
        match = START.fullmatch(lines[index].rstrip('\r\n'))
        if not match:
            if re.fullmatch(r"# <<< termux-containers [0-9a-f]{16} <<<", lines[index].rstrip('\r\n')):
                raise ValueError("自启动块缺少起始标记，拒绝修改")
            result.append(lines[index])
            index += 1
            continue
        marker = match[1]
        end = f"# <<< termux-containers {marker} <<<"
        stop = index + 1
        while stop < len(lines) and lines[stop].rstrip('\r\n') != end:
            if START.fullmatch(lines[stop].rstrip('\r\n')):
                raise ValueError("自启动块嵌套或结束标记缺失，拒绝修改")
            stop += 1
        block = lines[index:stop + 1]
        owned = any(line.startswith(owner) for line in block)
        if stop == len(lines):
            raise ValueError("自启动块结束标记缺失，拒绝修改")
        if marker in recorded_markers and not owned:
            raise ValueError("已记录自启动块的入口发生变化，拒绝修改")
        if owned:
            body = [line.rstrip('\r\n') for line in block]
            if (len(body) != 5 or body[1] != 'case $- in' or body[3] != 'esac'
                    or not body[2].startswith(owner) or not body[2].endswith(' ) & ;;')):
                raise ValueError("本仓库自启动块已被修改，拒绝删除")
            tokens = shlex.split(body[2][len(owner):-len(' ) & ;;')])
            if (len(tokens) != 7 or tokens[1:3] != ['start', '>>']
                    or tokens[4:] != ['2>&1', '<', '/dev/null']):
                raise ValueError("本仓库自启动命令已被修改，拒绝删除")
            if hashlib.sha256(tokens[0].encode()).hexdigest()[:16] != marker:
                raise ValueError("自启动配置路径与标记不匹配，拒绝删除")
        else:
            result.extend(block)
        index = stop + 1
    return ''.join(result)


def uninstall(yes):
    recorded = RECORD.exists()
    data = load_record()
    home = Path.home()
    paths = {home / name: set() for name in (".bashrc", ".bash_profile", ".bash_login", ".profile", ".zshrc")}
    paths.setdefault(Path(os.environ.get("ZDOTDIR", str(home))) / ".zshrc", set())
    for entry in data["shells"]:
        paths.setdefault(Path(entry["path"]), set()).add(entry["marker"])
    target = Path(os.environ["PREFIX"]) / "bin/termux-containers"
    if data["command"] is not None and data["command"] != str(target):
        raise ValueError("安装记录的命令入口与当前 PREFIX 不一致，请恢复安装时的 PREFIX")
    print(f"卸载仓库: {ROOT}")
    print("将检查以下 Shell 文件，仅移除指向本仓库的完整自启动块：")
    for path in sorted(paths):
        print(f"  {path}")
    print(f"将移除属于本仓库的命令入口: {target}")
    print(f"将移除虚拟环境: {ROOT / '.venv'}")
    print("保留仓库、YAML、挂载数据、容器、运行中的服务、状态元数据、日志和系统依赖。")
    print("卸载前如需停止服务，请先执行 termux-containers stop。")
    if not recorded:
        print("未找到安装记录：仅检查标准 Shell 文件及当前 ZDOTDIR，历史自定义路径需手动检查。")
    if not yes:
        if not sys.stdin.isatty():
            raise ValueError("非交互卸载需要 --yes")
        if input("确认卸载？[y/N] ").strip().lower() not in ("y", "yes"):
            print("已取消")
            return 0
    failures = []
    for path, markers in paths.items():
        try:
            if not path.exists():
                if path.is_symlink():
                    raise ValueError("启动文件为失效符号链接")
                continue
            content = path.read_text(encoding="utf-8")
            cleaned = clean_shell(content, markers)
            if cleaned != content:
                path.write_text(cleaned, encoding="utf-8")
                print(f"已移除自启动块: {path}")
        except (OSError, UnicodeError, ValueError) as exc:
            failures.append(f"{path}: {exc}")
    try:
        if target.is_symlink():
            raise ValueError("命令入口为符号链接，拒绝删除")
        if target.exists():
            if target.read_text(encoding="utf-8") == wrapper_content():
                target.unlink()
                print(f"已移除命令入口: {target}")
            elif data["command"] is not None:
                raise ValueError("已记录命令入口不再属于本仓库或已被修改，拒绝删除")
            else:
                print(f"保留其他来源的命令入口: {target}")
    except (OSError, UnicodeError, ValueError) as exc:
        failures.append(f"{target}: {exc}")
    venv = ROOT / ".venv"
    try:
        if venv.is_symlink():
            raise ValueError(".venv 是符号链接，拒绝删除")
        if venv.exists():
            if not venv.is_dir() or not (venv / "pyvenv.cfg").is_file():
                raise ValueError(".venv 不是可识别的 Python 虚拟环境，拒绝删除")
            shutil.rmtree(venv)
            print(f"已移除虚拟环境: {venv}")
    except (OSError, ValueError) as exc:
        failures.append(f"{venv}: {exc}")
    if not failures:
        try:
            RECORD.unlink(missing_ok=True)
        except OSError as exc:
            failures.append(f"{RECORD}: {exc}")
    if failures:
        for failure in failures:
            print(f"清理失败: {failure}", file=sys.stderr)
        print("卸载未全部完成，已保留安装记录（如有），可修复后重试。", file=sys.stderr)
        return 1
    print("工具卸载完成；容器和用户数据未删除，运行中的服务未停止。")
    return 0


def main():
    parser = argparse.ArgumentParser(description="卸载 Termux containers 工具，保留容器与用户数据")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = parser.parse_args()
    try:
        return uninstall(args.yes)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("卸载已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
