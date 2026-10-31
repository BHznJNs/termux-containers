from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


class StateError(RuntimeError):
    pass


def state_root():
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    return base / "termux-containers"


@contextmanager
def project_lock(project_id):
    try:
        import fcntl
    except ImportError as exc:
        raise StateError("生命周期命令仅支持 Termux/Linux（需要 flock）") from exc
    directory = state_root() / project_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "project.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StateError("同一配置已有管理操作正在执行，本次未执行") from exc
        try:
            yield directory
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Metadata:
    def __init__(self, directory, config_path):
        self.path = directory / "metadata.json"
        self.config_path = str(config_path)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"config": self.config_path, "services": {}}
        except (OSError, ValueError) as exc:
            raise StateError(f"配置元数据无法读取，拒绝管理现有容器: {exc}") from exc
        if (not isinstance(data, dict) or data.get("config") != self.config_path
                or not isinstance(data.get("services"), dict)):
            raise StateError("配置元数据不匹配或格式损坏")
        for name, record in data["services"].items():
            if (not isinstance(record, dict) or not isinstance(record.get("image"), str)
                    or not isinstance(record.get("fingerprint"), str)):
                raise StateError(f"服务元数据损坏: {name}")
        self.services = data["services"]

    def save(self):
        payload = {"config": self.config_path, "services": self.services}
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix="metadata-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def record(self, service, fingerprint):
        self.services[service.name] = {"image": service.image, "fingerprint": fingerprint}
        self.save()
