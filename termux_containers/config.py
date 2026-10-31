from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re

import yaml


class ConfigError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise ConfigError("YAML 对象的键必须为字符串")
        if key in result:
            raise ConfigError(f"YAML 键重复: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class Volume:
    source: Path
    target: str


@dataclass(frozen=True)
class Service:
    name: str
    image: str
    enabled: bool
    volumes: tuple[Volume, ...]
    environment: dict[str, str]

    @property
    def fingerprint(self):
        value = {"environment": self.environment,
                 "volumes": [(str(v.source), v.target) for v in self.volumes]}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    path: Path
    services: dict[str, Service]

    @property
    def project_id(self):
        return hashlib.sha256(str(self.path).encode()).hexdigest()[:16]

    def container_name(self, service):
        return f"tc-{self.project_id}-{service}"


def _text(value, context):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ConfigError(f"{context} 必须为不含控制字符的非空字符串")
    return value


def check_directory(path):
    current = path
    while not current.exists():
        if current.is_symlink():
            raise ConfigError(f"绑定路径包含失效符号链接: {current}")
        parent = current.parent
        if parent == current:
            raise ConfigError(f"无法访问绑定路径: {path}")
        current = parent
    if not current.is_dir():
        raise ConfigError(f"首版仅支持目录绑定，路径不是目录: {current}")
    if not os.access(current, os.R_OK | os.W_OK | os.X_OK):
        raise ConfigError(f"绑定路径不可读写或不可遍历: {current}")


def load_config(path):
    path = Path(path).expanduser().resolve()
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise ConfigError(f"无法读取配置 {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"services"} or not isinstance(data["services"], dict):
        raise ConfigError("配置必须且只能包含 services 对象")
    services = {}
    ports = {}
    for name, raw in data["services"].items():
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}", name):
            raise ConfigError(f"无效服务名称: {name!r}")
        if not isinstance(raw, dict):
            raise ConfigError(f"{name}: 服务必须为对象")
        unknown = set(raw) - {"image", "enabled", "volumes", "environment"}
        if unknown:
            raise ConfigError(f"{name}: 不支持的字段: {', '.join(sorted(unknown))}")
        image = _text(raw.get("image"), f"{name}.image")
        component = r"[a-z0-9]+(?:(?:[._]|__|[-]+)[a-z0-9]+)*"
        registry = r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?(?::[0-9]+)?/)"
        reference = (rf"(?:{registry})?{component}(?:/{component})*"
                     r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?"
                     r"(?:@sha256:[a-fA-F0-9]{64})?")
        if not re.fullmatch(reference, image):
            raise ConfigError(f"{name}: image 必须为有效 OCI 镜像引用，不支持本地路径或 URL")
        enabled = raw.get("enabled", True)
        if type(enabled) is not bool:
            raise ConfigError(f"{name}.enabled 必须为布尔值")
        environment = raw.get("environment", {})
        if not isinstance(environment, dict):
            raise ConfigError(f"{name}.environment 必须为对象")
        for key, value in environment.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not isinstance(value, str) or '\x00' in value:
                raise ConfigError(f"{name}: 环境变量名称无效或值不是字符串: {key!r}")
            if len(f"{key}={value}".encode()) >= 131072:
                raise ConfigError(f"{name}: 环境变量过长: {key}")
        port = environment.get("PORT")
        if port is not None and enabled:
            if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
                raise ConfigError(f"{name}: PORT 必须为 1-65535 的字符串")
            number = int(port)
            if number in ports:
                raise ConfigError(f"{name} 与 {ports[number]} 声明相同 PORT={number}，PRoot 共享宿主网络")
            ports[number] = name
        volumes_raw = raw.get("volumes", [])
        if not isinstance(volumes_raw, list):
            raise ConfigError(f"{name}.volumes 必须为字符串数组")
        volumes = []
        targets = []
        for item in volumes_raw:
            item = _text(item, f"{name}.volumes")
            if item.count(':') != 1:
                raise ConfigError(f"{name}: 绑定格式必须为 宿主目录:/容器目录: {item!r}")
            source, target = item.split(':')
            if not source or not target.startswith('/') or '..' in PurePosixPath(target).parts:
                raise ConfigError(f"{name}: 无效绑定: {item!r}")
            target_path = PurePosixPath(target)
            if str(target_path) == '/' or any(target_path == t or target_path in t.parents or t in target_path.parents for t in targets):
                raise ConfigError(f"{name}: 绑定目标重复、嵌套或覆盖根目录: {target}")
            targets.append(target_path)
            source_path = Path(source).expanduser()
            if not source_path.is_absolute():
                source_path = path.parent / source_path
            check_directory(source_path)
            source_path = source_path.resolve()
            volumes.append(Volume(source_path, str(target_path)))
        services[name] = Service(name, image, enabled, tuple(volumes), environment)
    return Config(path, services)
