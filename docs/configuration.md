# 配置参考

[返回 README](../README.md)

## 配置文件与路径

首次安装的 `containers.yaml` 使用 `services: {}`，不自动下载任何镜像。默认配置始终是**克隆仓库根目录**的 `containers.yaml`，与调用时当前目录无关。可参考 [示例配置](../containers.example.yaml) 编辑。

所有命令均支持 `-f`，可放在子命令之前或之后：

```sh
termux-containers -f ~/services/containers.yaml apply
termux-containers init -f ~/services/containers.yaml
```

`-f` 本身的相对路径按当前目录定位；YAML 内宿主绑定相对路径按 YAML 所在目录解析。

## 字段

| 字段 | 规则 |
| --- | --- |
| `services` | 必填对象，可为空；服务名为字母/数字开头，允许字母、数字、`_`、`.`、`-`，最长 63 字符 |
| `image` | 必填 OCI 引用，支持标签和 sha256 digest；不支持 URL、本地归档 |
| `enabled` | 布尔值，默认 `true` |
| `volumes` | 文件或目录挂载数组，支持 `宿主路径:/容器绝对路径` 字符串及显式类型对象，默认空 |
| `environment` | 环境变量对象，值必须为字符串（数字、布尔值需加引号），默认空 |

未知字段、重复 YAML 键及重复/嵌套容器绑定目标会被拒绝。`command`、`working_dir`、`depends_on`、`healthcheck` 留待后续版本，不会静默忽略。

## 文件与目录挂载

```yaml
volumes:
  - ./data:/app/data
  - ./existing-config.yaml:/app/config.yaml
  - type: file
    source: ./settings.json
    target: /app/settings.json
  - type: directory
    source: ./logs
    target: /app/logs
```

- 字符串写法自动识别已存在的普通文件或目录；路径不存在时按目录处理，**不根据扩展名猜测类型**。
- 对象写法必须且只能包含 `type`、`source`、`target`；`type` 为 `file` 或 `directory`。
- `type: file` 的宿主文件必须事先存在，否则整体配置校验失败；不会创建空文件或文件的父目录。建议配置文件使用显式文件声明，避免拼错路径时被创建为目录。
- `type: directory` 的宿主目录不存在时，启动前自动创建，包括父目录。
- 类型不符、特殊文件（如 FIFO/设备）、失效符号链接及路径权限不足会报错。文件要求可读写，目录要求可读写和可遍历；首版不提供只读挂载选项。
- 有效符号链接解析到其实际文件或目录；路径不支持冒号。

已有宿主文件绝不初始化或覆盖，已有宿主数据不删除；容器内应用仍可修改绑定文件。挂载类型、路径或目标改变后执行 `apply` 会重启对应服务，不会重建容器。文件内容变化本身不触发重启，应用是否自动重载取决于其实现。

绑定会遮蔽镜像目标路径原内容，不会复制镜像内容到宿主机。示例 Web 目录需要用户自行放入页面。

## 网络与端口

`PORT` 仅是传给应用的环境变量，不是 Docker 端口映射，应用必须自行支持该变量。PRoot 与 Termux 共享网络，两个启用服务声明相同 `PORT` 时会提前拒绝；无法静态检测镜像内部默认端口或设备其他进程占用，应用需使用非特权端口。
