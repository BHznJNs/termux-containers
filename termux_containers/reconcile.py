import sys

from .config import ConfigError, check_directory
from .runtime import RuntimeError_
from .state import Metadata, StateError, project_lock


def execute(config, runtime, command, names):
    unknown = set(names) - config.services.keys()
    if unknown:
        raise ConfigError(f"未知服务: {', '.join(sorted(unknown))}")
    selected = [config.services[n] for n in dict.fromkeys(names)] if names else list(config.services.values())
    with project_lock(config.project_id) as directory:
        metadata = Metadata(directory, config.path)
        installed = runtime.installed()
        running = runtime.running()
        if command == "status":
            print(f"{'SERVICE':<24} {'STATUS':<16} IMAGE / CONTAINER")
            for service in selected:
                name = config.container_name(service.name)
                state = "Running" if name in running else "Stopped" if name in installed else "Not installed"
                print(f"{service.name:<24} {state:<16} {service.image} / {name}"
                      + (" [disabled]" if not service.enabled else ""))
            return 0
        failures = 0
        for service in selected:
            try:
                _service(config, runtime, metadata, command, service)
            except (OSError, ConfigError, RuntimeError_, StateError) as exc:
                failures += 1
                print(f"{service.name}: {exc}", file=sys.stderr)
        return 1 if failures else 0


def _service(config, runtime, metadata, command, service):
    name = config.container_name(service.name)
    installed = name in runtime.installed()
    record = metadata.services.get(service.name)
    if installed and record is None:
        raise StateError(f"容器 {name} 已存在但没有归属记录，拒绝接管；请检查元数据或手动迁移该容器")
    if command == "stop" or (command == "apply" and not service.enabled):
        if installed:
            runtime.stop(name)
        print(f"{service.name}: 已停止" if installed else f"{service.name}: 未安装")
        return
    if not service.enabled:
        print(f"{service.name}: 已禁用，跳过")
        return
    if command == "start" and not installed:
        print(f"{service.name}: 未安装，跳过；请运行 apply")
        return
    if command == "start" and record["image"] != service.image:
        raise ConfigError("镜像声明已变化，请运行 apply 重新部署")
    for volume in service.volumes:
        check_directory(volume.source)
        volume.source.mkdir(parents=True, exist_ok=True)
        check_directory(volume.source)
    if command == "apply" and installed and record["image"] != service.image:
        print(f"{service.name}: 镜像变更，重部署（仅保留宿主机绑定数据）", flush=True)
        runtime.stop(name)
        runtime.remove(name)
        installed = False
    if not installed:
        # Persist ownership before install, so an interrupted install remains recoverable.
        metadata.record(service, "")
        runtime.install(name, service.image)
        if name not in runtime.installed():
            raise RuntimeError_("安装命令结束但未发现容器")
        record = metadata.services[service.name]
    running = name in runtime.running()
    if running and command == "apply" and record["fingerprint"] != service.fingerprint:
        runtime.stop(name)
        running = False
    if running:
        print(f"{service.name}: 已运行，无需重复启动")
        return
    runtime.start(name, service)
    metadata.record(service, service.fingerprint)
    print(f"{service.name}: 已启动")
