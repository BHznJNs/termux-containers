# Termux containers

基于 PRoot-Distro 的轻量级声明式 OCI 服务管理工具。无需 Docker 守护进程，仅在 CLI 调用或 Termux Session 启动时协调服务。

## 安装

在 Android **Termux** 中使用。Python 需要 3.10+，PRoot-Distro 需要支持 OCI 镜像及 `run --detach`、`list --quiet`、`ps`、`kill` 的新版；旧版仅支持发行版插件的 PRoot-Distro 不可用。

1. `pkg install git`
2. 手动 `git clone <本仓库地址>`，进入克隆目录。
3. `bash install.sh`

安装脚本通过 `pkg` 安装 Python、PRoot、PRoot-Distro，在仓库 `.venv` 安装 PyYAML，并创建 `$PREFIX/bin/termux-containers` 命令。随后执行 `init`，检查运行时能力、创建默认空配置并配置当前 Bash/Zsh 的 Session 自启动。初始化不会覆盖已有 YAML；重复安装可更新依赖和启动入口。

仓库必须放在 Termux 私有目录（例如 `$HOME/termux-containers`），不要放在 `/sdcard`。安装后不要移动仓库；移动后需重新安装，同时注意配置路径决定项目身份。系统包仍是旧版时，请先按 [PRoot-Distro 官方说明](https://github.com/termux/proot-distro) 安装新版，再重新执行安装脚本；本项目不静默替换系统运行时。

也可直接使用仓库入口：`bash ./termux-containers status`。不提供 PyPI 发布、Docker 安装或 Web UI。

## 配置与使用

首次安装的 `containers.yaml` 使用 `services: {}`，不自动下载任何镜像。参考 `containers.example.yaml` 编辑该文件：

```yaml
services:
  web:
    image: nginxinc/nginx-unprivileged:stable-alpine
    enabled: true
    volumes:
      - ./data/web:/usr/share/nginx/html
    environment:
      PORT: "8080"
```

```sh
termux-containers apply
termux-containers status
termux-containers stop web
termux-containers start web
termux-containers -f ~/services/containers.yaml apply
# -f 也可放在子命令之后
termux-containers init -f ~/services/containers.yaml
```

所有生命周期命令可传一个或多个服务名，不传则处理全部配置服务。默认配置始终是**克隆仓库根目录**的 `containers.yaml`，与调用时当前目录无关。`-f` 本身的相对路径按当前目录定位；YAML 内宿主绑定相对路径按 YAML 所在目录解析。

### 首版字段

| 字段 | 规则 |
| --- | --- |
| `services` | 必填对象，可为空；服务名为字母/数字开头，允许字母、数字、`_`、`.`、`-`，最长 63 字符 |
| `image` | 必填 OCI 引用，支持标签和 sha256 digest；不支持 URL、本地归档 |
| `enabled` | 布尔值，默认 `true` |
| `volumes` | `宿主目录:/容器绝对目录` 字符串数组，默认空 |
| `environment` | 环境变量对象，值必须为字符串（数字、布尔值需加引号），默认空 |

未知字段、重复 YAML 键、重复/嵌套容器绑定目标及文件绑定会被拒绝。`command`、`working_dir`、`depends_on`、`healthcheck` 留待后续版本，不会静默忽略。

缺失宿主目录在启动前自动创建，已有文件绝不覆盖，已有宿主数据不删除。首版统一将每条绑定解释为目录，不提供文件类型推断或文件初始化。空绑定目录会遮蔽镜像对应目录原内容；示例 Web 目录需要用户自行放入页面，不会自动复制镜像内容。

`PORT` 仅是传给应用的环境变量，不是 Docker 端口映射，应用必须自行支持该变量。PRoot 与 Termux 共享网络，两个启用服务声明相同 `PORT` 时会提前拒绝；无法静态检测镜像内部默认端口或设备其他进程占用，应用需使用非特权端口。

## 生命周期语义

| 情况 | `apply` |
| --- | --- |
| 启用且未安装 | 安装并运行 OCI 的 Entrypoint/Cmd |
| 已安装、已停止 | 启动 |
| 已运行、配置一致 | 不操作 |
| 环境变量或绑定变化 | 停止后重新启动，不重建文件系统 |
| 镜像引用或标签变化 | 停止、删除对应容器文件系统，重新安装启动 |
| `enabled: false` | 停止，不安装、不删除 |
| 服务从 YAML 移除 | 不停止、不删除，留待显式处理 |

**镜像变更重部署会删除容器内部所有未绑定数据。** 持久化内容必须使用宿主目录绑定。安装失败时返回错误，可修复后重复执行 `apply`；不承诺回滚旧镜像。相同标签不检查远端更新，不提供 `--pull`。

- `start` 只启动启用且已安装的服务，绝不下载镜像；已运行的服务不因配置变化重启。已安装镜像与声明不符时提示执行 `apply`。停止状态下启动使用当前绑定和环境变量。
- `stop` 停止项目容器全部会话，不删除文件系统或绑定数据。单个服务失败不阻止其他服务，最终退出码非零。
- `status` 直接通过 PRoot-Distro 查询 `Running` / `Stopped` / `Not installed`；运行不代表健康检查通过。
- 配置在管理操作前整体校验；无效配置不会执行安装、停止或删除。权限在每个服务启动前再次检查。

## 并发、归属与元数据

配置文件规范绝对路径的哈希决定项目身份，容器命名为 `tc-<项目哈希>-<服务名>`。不同配置互不影响，同一配置的管理操作使用非阻塞文件锁串行化；竞争调用返回非零，不重复执行。锁在进程退出时由系统释放。

`${XDG_STATE_HOME:-$HOME/.local/state}/termux-containers/<项目哈希>/metadata.json` 只记录配置来源、容器归属、安装镜像引用和上次成功启动的配置指纹，**不存运行状态或环境变量明文**。元数据原子写入。若同名容器存在但没有归属记录，拒绝接管，以免修改无关容器。不要手动改动运行时容器或删除元数据；状态检测不会探测外部对容器镜像内容的修改。

配置文件移动/改名会产生新项目；原项目容器不会自动删除。移除服务前如需停止，应先运行 `stop 服务名` 或设置 `enabled: false` 后 `apply`。后续清理可使用 `status` 所显示的完整名称显式执行 PRoot-Distro 命令；手动删除前确认目标及数据备份。不要用全局 `kill --all` 清理项目。

## Session 自启动

`init` 为当前 `$SHELL` 的 Bash 或 Zsh 写入带标记启动块，只在交互 Shell 中后台执行固定配置的 `start`，不阻塞 Shell，不下载镜像，不自动重启已运行服务。Bash 同时覆盖 `.bashrc` 及当前生效的登录 profile；Zsh 尊重 `$ZDOTDIR`。重复初始化更新对应标记块，保留其他内容；切换 Shell 后重新执行 `init`。不同 `-f` 初始化的项目各有入口。

日志追加到 `${XDG_STATE_HOME:-$HOME/.local/state}/termux-containers/autostart.log`，可按需手动轮转。取消自启动时删除相关启动文件中的 `# >>> termux-containers ... >>>` 至对应结束标记块。

Session 自启动不等于 Android 开机自启。Android 休眠、内存回收或系统限制仍可能终止服务；本工具不是常驻监督器。按需配置 Termux 的电池优化豁免和 wake lock。

## 限制与故障定位

PRoot 不提供 Docker 的内核、网络或安全隔离，不支持依赖 systemd、特权能力、特定内核功能的全部 OCI 镜像。只运行可信配置和镜像。设备架构必须有可用镜像，本项目首版不配置跨架构仿真。

后台执行复用 PRoot-Distro 的 `run --detach`，其默认丢弃容器 stdout/stderr。启动检查只确认短暂存活，不是健康检查；需持久日志时由应用写入绑定目录。启动失败可先 `termux-containers stop 服务名`，再按 `status` 显示的容器名手动前台执行 `proot-distro run`，补上 YAML 对应的 `--bind` 和 `--env` 参数定位问题（环境变量可能包含敏感值，不要直接公开终端记录）。

## 代码布局

- `config.py`：YAML 解析、严格校验、路径与配置指纹。
- `runtime.py`：PRoot-Distro CLI 适配，解析实际安装/会话状态。
- `state.py`：项目锁、原子配置元数据。
- `reconcile.py`：无守护进程的服务协调逻辑，可由后续 Web API 复用。
- `setup.py`：Termux 环境检查、默认配置和 Shell 启动块。
- `cli.py`：CLI 参数与退出码处理。

按首版要求不包含测试。开发阶段可做 Python 静态语法检查；Android/Termux 实机运行需在目标设备确认。
