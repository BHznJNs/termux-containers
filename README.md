# Termux containers

基于 PRoot-Distro 的 Termux 声明式 OCI 容器管理工具，无需常驻守护进程。

## 安装

在 Android **Termux** 中执行，需要 Python 3.10+ 和支持 OCI、`run --detach`、`ps`、`kill` 的新版 PRoot-Distro。

```sh
pkg install git
git clone <本仓库地址> ~/termux-containers
cd ~/termux-containers
bash install.sh
```

请将 `<本仓库地址>` 替换为实际地址，仓库应放在 Termux 私有目录，不要放在 `/sdcard`。脚本会安装依赖、创建命令入口和默认空配置，并配置 Bash/Zsh Session 自启动。

## 配置示例

编辑仓库根目录的 `containers.yaml`，然后执行 `termux-containers apply`：

```yaml
services:
  web:
    image: nginxinc/nginx-unprivileged:stable-alpine
    enabled: true
    volumes:
      - type: directory
        source: ./data/web
        target: /usr/share/nginx/html
      # 文件挂载：先创建有效配置文件，再取消以下注释。
      # - type: file
      #   source: ./config/default.conf
      #   target: /etc/nginx/conf.d/default.conf
    environment:
      PORT: "8080"
```

相对挂载路径以 YAML 所在目录为基准。缺失目录自动创建，文件必须事先存在；示例页面需自行放入 `data/web`。`PORT` 是应用环境变量，不是端口映射。

通过 `command` 传入容器启动命令或参数，推荐使用数组：

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    command:
      - tunnel
      - --no-autoupdate
      - run
      - --token
      - YOUR_TUNNEL_TOKEN
```

也支持等价的字符串写法：

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run --token YOUR_TUNNEL_TOKEN
```

## 命令列表

| 命令 | 作用 |
| --- | --- |
| `termux-containers init` | 初始化环境、默认配置和 Session 自启动，不覆盖已有配置 |
| `termux-containers apply [服务名 ...]` | 应用配置：安装缺失服务、启动、重启、重部署或停止禁用服务 |
| `termux-containers start [服务名 ...]` | 启动已安装且启用的服务，不下载镜像、不重复启动 |
| `termux-containers stop [服务名 ...]` | 停止服务，保留容器文件系统和宿主挂载数据 |
| `termux-containers status [服务名 ...]` | 查看配置中服务的实际安装和运行状态 |
| `termux-containers --help` | 查看帮助；子命令也支持 `--help` |
| `bash uninstall.sh [--yes]` | 在仓库目录卸载工具和自启动入口，保留容器与数据；`--yes` 跳过确认 |

生命周期命令省略服务名表示处理全部配置服务。CLI 默认读取仓库根目录的 `containers.yaml`，支持用 `-f` 指定配置，例如 `termux-containers -f ~/services/containers.yaml apply`。

**注意：修改镜像引用后执行 `apply` 会重建对应容器，丢失容器内未挂载的数据。**

详细文档：[配置参考](docs/configuration.md) · [安装细节与运维](docs/operations.md) · [开发与内部机制](docs/development.md)
