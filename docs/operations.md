# 安装细节与运维

[返回 README](../README.md)

## 安装细节

运行环境为 Android Termux、Python 3.10+，以及支持 OCI 镜像、`run --detach`、`list --quiet`、`ps`、`kill` 的新版 PRoot-Distro；旧版仅支持发行版插件的 PRoot-Distro 不可用。

`bash install.sh` 通过 `pkg` 安装 Python、PRoot、PRoot-Distro，在仓库 `.venv` 安装 PyYAML，并创建 `$PREFIX/bin/termux-containers` 命令。随后执行 `init`，检查运行时能力、创建默认空配置并配置当前 Bash/Zsh 的 Session 自启动。初始化不会覆盖已有 YAML；重复安装可更新依赖和启动入口。

仓库必须放在 Termux 私有目录（例如 `$HOME/termux-containers`），不要放在 `/sdcard`。安装后不要移动仓库；移动后需重新安装，同时注意配置路径决定项目身份。系统包仍是旧版时，请先按 [PRoot-Distro 官方说明](https://github.com/termux/proot-distro) 安装新版，再重新执行安装脚本；本项目不静默替换系统运行时。

也可直接使用仓库入口：`bash ./termux-containers status`。不提供 PyPI 发布、Docker 安装或 Web UI。

## 卸载工具

在原克隆仓库目录执行：

```sh
bash uninstall.sh
# 非交互执行，跳过确认：
bash uninstall.sh --yes
```

脚本在 Termux 中使用 `$PREFIX/bin/python`，不依赖仓库虚拟环境、YAML 或 PRoot-Distro 是否可用。执行前列出检查和清理范围，默认要求交互确认；可用 `--help` 查看参数。

卸载仅移除明确指向本仓库的 Shell 自启动块、`$PREFIX/bin/termux-containers` 命令包装器和仓库 `.venv`。**不会停止运行中的服务，也不会删除容器文件系统、仓库、YAML、宿主挂载数据、状态元数据、日志或系统依赖。** 如需停止服务，请在卸载前对各项目执行 `termux-containers -f 配置路径 stop`。

安装及 `init` 将命令入口、Shell 文件和配置标记记录在仓库 `.installation.json`。重复 `init -f` 会合并记录，卸载也会清理已记录的历史 Shell 路径。没有安装记录时，仅检查标准 Bash/Zsh 启动文件和当前 `ZDOTDIR`，依据块内本仓库路径识别归属；历史自定义 `ZDOTDIR` 需手动检查，不会扫描用户目录。

已修改的命令包装器、不完整或修改过的自启动块、符号链接命令入口，以及无法识别或为符号链接的 `.venv` 会保留并报错。各独立项会继续清理；全部成功后删除安装记录，部分失败返回非零并保留记录，可修复后重复执行。不要同时进行安装、初始化、卸载或其他管理操作。

保留容器归属元数据是为了重新安装后继续管理现有容器；不要仅删除元数据而保留容器，否则程序会拒绝接管无归属记录的同名容器。

## 生命周期语义

所有生命周期命令可传一个或多个服务名，不传则处理全部配置服务，例如：

```sh
termux-containers apply
termux-containers status
termux-containers stop web
termux-containers start web
```

| 情况 | `apply` |
| --- | --- |
| 启用且未安装 | 安装并运行 OCI 的 Entrypoint/Cmd |
| 已安装、已停止 | 启动 |
| 已运行、配置一致 | 不操作 |
| 环境变量或绑定变化 | 停止后重新启动，不重建文件系统 |
| 镜像引用或标签变化 | 停止、删除对应容器文件系统，重新安装启动 |
| `enabled: false` | 停止，不安装、不删除 |
| 服务从 YAML 移除 | 不停止、不删除，留待显式处理 |

**镜像变更重部署会删除容器内部所有未绑定数据。** 持久化内容必须使用宿主文件或目录绑定。安装失败时返回错误，可修复后重复执行 `apply`；不承诺回滚旧镜像。相同标签不检查远端更新，不提供 `--pull`。

- `start` 只启动启用且已安装的服务，绝不下载镜像；已运行的服务不因配置变化重启。已安装镜像与声明不符时提示执行 `apply`。停止状态下启动使用当前绑定和环境变量。
- `stop` 停止项目容器全部会话，不删除文件系统或绑定数据。单个服务失败不阻止其他服务，最终退出码非零。
- `status` 直接通过 PRoot-Distro 查询 `Running` / `Stopped` / `Not installed`；运行不代表健康检查通过。
- 配置在管理操作前整体校验；无效配置不会执行安装、停止或删除。权限在每个服务启动前再次检查。

配置文件移动/改名会产生新项目；原项目容器不会自动删除。移除服务前如需停止，应先运行 `stop 服务名` 或设置 `enabled: false` 后 `apply`。后续清理可使用 `status` 所显示的完整名称显式执行 PRoot-Distro 命令；手动删除前确认目标及数据备份。不要用全局 `kill --all` 清理项目。

## Session 自启动

`init` 为当前 `$SHELL` 的 Bash 或 Zsh 写入带标记启动块，只在交互 Shell 中后台执行固定配置的 `start`，不阻塞 Shell，不下载镜像，不自动重启已运行服务。Bash 同时在 `.bashrc` 及当前生效的登录 profile 中写入启动块；Zsh 尊重 `$ZDOTDIR`。重复初始化更新对应标记块，保留其他内容；切换 Shell 后重新执行 `init`。不同 `-f` 初始化的项目各有入口。

日志追加到 `${XDG_STATE_HOME:-$HOME/.local/state}/termux-containers/autostart.log`，可按需手动轮转。取消自启动时删除相关启动文件中的 `# >>> termux-containers ... >>>` 至对应结束标记块。

Session 自启动不等于 Android 开机自启。Android 休眠、内存回收或系统限制仍可能终止服务；本工具不是常驻监督器。按需配置 Termux 的电池优化豁免和 wake lock。

## 限制与故障定位

PRoot 不提供 Docker 的内核、网络或安全隔离，不支持依赖 systemd、特权能力、特定内核功能的全部 OCI 镜像。只运行可信配置和镜像。设备架构必须有可用镜像，本项目首版不配置跨架构仿真。

后台执行复用 PRoot-Distro 的 `run --detach`，其默认丢弃容器 stdout/stderr。启动检查只确认短暂存活，不是健康检查；需持久日志时由应用写入绑定目录。启动失败可先 `termux-containers stop 服务名`，再按 `status` 显示的容器名手动前台执行 `proot-distro run`，补上 YAML 对应的 `--bind` 和 `--env` 参数定位问题（环境变量可能包含敏感值，不要直接公开终端记录）。

项目锁与元数据的说明见 [开发与内部机制](development.md)。
