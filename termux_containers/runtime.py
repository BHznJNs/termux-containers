import os
import re
import shutil
import subprocess
import time


class RuntimeError_(RuntimeError):
    pass


_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ProotDistro:
    def __init__(self):
        self.executable = shutil.which("proot-distro")
        if not self.executable:
            raise RuntimeError_("未找到 proot-distro，请先运行 init")

    def call(self, *args, capture=False):
        env = dict(os.environ, NO_COLOR="1", TERM="dumb", COLUMNS="240")
        try:
            result = subprocess.run(
                [self.executable, *args], env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.STDOUT if capture else None,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            raise RuntimeError_(f"无法执行 PRoot-Distro: {exc}") from exc
        output = _ANSI.sub('', result.stdout or '')
        if result.returncode:
            raise RuntimeError_(f"proot-distro {' '.join(args[:2])} 失败（退出码 {result.returncode}）"
                                + (f"\n{output.strip()}" if output else ""))
        return output

    def verify(self):
        requirements = {
            "install": ("--name",), "list": ("--quiet",),
            "run": ("--detach", "--env", "--bind"),
            "ps": ("--quiet",), "kill": ("--all",),
        }
        for command, tokens in requirements.items():
            output = self.call(command, "--help", capture=True)
            if not all(token.lower() in output.lower() for token in tokens):
                raise RuntimeError_(f"PRoot-Distro 不支持所需的 {command} 接口；请安装支持 OCI/run/ps/kill 的新版后重试")
        self.installed()
        self.running()

    def installed(self):
        output = self.call("list", "--quiet", capture=True)
        names = set()
        for line in output.splitlines():
            line = line.strip()
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", line):
                names.add(line)
            elif line:
                raise RuntimeError_(f"无法解析 proot-distro list --quiet 输出: {line!r}")
        return names

    def running(self):
        output = self.call("ps", capture=True)
        names = set()
        header = False
        empty = False
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[:2] == ["PID", "CONTAINER"]:
                header = True
            elif fields and fields[0].isascii() and fields[0].isdigit():
                if not header or len(fields) < 3 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", fields[1]):
                    raise RuntimeError_("无法解析 proot-distro ps 会话行")
                names.add(fields[1])
            elif "No active sessions." in line:
                empty = True
        if not header and not empty:
            raise RuntimeError_("无法识别 proot-distro ps 输出，请检查 PRoot-Distro 版本")
        return names

    def install(self, name, image):
        self.call("install", "--name", name, image)

    def start(self, name, service):
        args = ["run", "--detach"]
        for volume in service.volumes:
            args.extend(["--bind", f"{volume.source}:{volume.target}"])
        for key, value in sorted(service.environment.items()):
            args.extend(["--env", f"{key}={value}"])
        args.append(name)
        self.call(*args)
        for _ in range(10):
            if name in self.running():
                time.sleep(0.2)
                if name in self.running():
                    return
            time.sleep(0.1)
        raise RuntimeError_(f"{name}: 启动后未保持运行；请前台执行 proot-distro run 检查镜像入口和服务配置")

    def stop(self, name):
        if name in self.running():
            self.call("kill", name)
            if name in self.running():
                raise RuntimeError_(f"{name}: 停止后仍存在活动会话")

    def remove(self, name):
        self.call("remove", name)
