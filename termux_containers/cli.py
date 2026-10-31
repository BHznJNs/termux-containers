import argparse
from pathlib import Path
import subprocess
import sys

from .config import ConfigError, load_config
from .reconcile import execute
from .runtime import ProotDistro, RuntimeError_
from .setup import initialize
from .state import StateError


ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(prog="termux-containers", description="Termux 声明式 OCI 容器管理")
    parser.add_argument("-f", "--file", default=str(ROOT / "containers.yaml"), help="YAML 配置路径")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("init", "初始化 Termux 环境和 Session 自启动"),
        ("start", "启动已安装且启用的服务，不下载镜像"),
        ("stop", "停止服务，保留文件系统和绑定数据"),
        ("status", "查询 PRoot-Distro 实际状态"),
        ("apply", "安装、重启或重部署以应用配置"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("-f", "--file", default=argparse.SUPPRESS, help="YAML 配置路径")
        if command != "init":
            subparser.add_argument("services", nargs="*", help="服务名称；默认全部")
    args = parser.parse_args(argv)
    try:
        path = Path(args.file).expanduser().resolve()
        if args.command == "init":
            initialize(path, ROOT / "termux-containers")
            return 0
        config = load_config(path)
        runtime = ProotDistro()
        return execute(config, runtime, args.command, args.services)
    except (ConfigError, RuntimeError_, StateError, OSError, subprocess.CalledProcessError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("操作已中断；可重新执行 apply 协调配置", file=sys.stderr)
        return 130
