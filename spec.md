# Termux containers — 项目目标与需求设计

## 1. 项目概述

**Termux containers** 是一个面向 Android Termux 环境的轻量级声明式容器管理工具，基于 PRoot-Distro 实现 OCI 容器的安装、配置和生命周期管理。

项目参考 Docker Compose 的使用体验，但不以完整兼容 Docker Compose 为目标。

用户通过一个 YAML 配置文件声明需要运行的容器及其配置，程序负责解析配置，并调用 PRoot-Distro 将实际运行环境调整至期望状态。

### 1.1 核心理念

- **声明式配置**：用户只需要描述期望运行的容器，不需要逐个编写安装和启动脚本。
- **配置即事实来源**：以 YAML 配置为唯一的用户配置来源
- **按需执行**：不依赖常驻守护进程，仅在用户主动调用或 Termux Session 启动时执行管理操作。
- **幂等操作**：重复执行相同操作不应导致不必要的容器重建或重复启动。
- **最小实现**：优先实现实际需要的功能，不追求 Docker 的完整特性。
- **CLI 优先**：所有核心功能通过 CLI 实现，Web UI 仅作为可选的交互界面。

### 1.2 目标使用场景

主要面向使用旧 Android 手机、平板等设备运行轻量级自托管服务的用户。

典型场景包括：

- 部署 API 代理和中转服务。
- 部署笔记同步服务。
- 部署其他可通过 OCI 镜像运行的轻量级服务。
- 通过单一配置文件维护多个服务。
- 在 Termux Session 启动时自动恢复服务。
- 修改配置后统一应用变更，无需手动管理单个容器。

---

## 2. 项目范围

### 2.1 核心功能

项目首版需要实现以下功能：

1. Termux 运行环境初始化。
2. 声明式容器配置解析与校验。
3. OCI 镜像安装与容器启动。
4. 宿主机目录绑定与初始化。
5. 容器生命周期管理。
6. 配置变更检测与应用。
7. Termux Session 启动时自动启动配置的容器。
8. 基础 CLI 操作入口。

---

## 3. 系统架构

项目由四个主要部分组成。

### 3.1 配置层

负责读取、解析和校验 YAML 配置文件。

配置文件包含：

- 容器名称。
- OCI 镜像地址和版本。
- 容器启用状态。
- 宿主机与容器目录绑定。
- 环境变量。
- 可选启动参数。

配置文件是用户管理容器的主要入口。

### 3.2 容器运行时适配层

负责封装 PRoot-Distro CLI。

主要操作包括：

- 安装 OCI 镜像。
- 查看容器和会话状态。
- 启动容器。
- 停止容器。
- 删除或重新创建容器。
- 向容器传递目录绑定、环境变量和启动参数。

不重新实现镜像下载和容器运行时。

### 3.3 配置协调层

负责比较期望配置与当前容器状态，决定需要执行哪些操作。

主要职责：

- 检测尚未安装的容器。
- 判断容器是否正在运行。
- 判断是否需要重新启动。
- 识别需要重新部署的容器。
- 避免影响无关容器。
- 在操作失败时报告错误。

不需要在后台持续运行。

### 3.4 用户交互层

首版提供 CLI，后续可添加 Web UI。

CLI 和 Web UI 应当复用相同的配置解析、协调和执行逻辑，避免重复实现业务功能。

---

## 4. 配置文件设计

### 4.1 配置格式

采用 YAML，并参考 Docker Compose 的 `services` 结构。

示例：

```yaml
services:
  cli-proxy:
    image: ghcr.io/example/cli-proxy:latest
    enabled: true

    volumes:
      - ./data/cli-proxy:/app/config
      - ./logs/cli-proxy:/app/logs

    environment:
      PORT: "8317"

  note-sync:
    image: example/note-sync:latest
    enabled: true

    volumes:
      - ./data/note-sync:/app/data

    environment:
      PORT: "3000"
```

上述镜像地址仅为示例。

### 4.2 配置字段

| 字段            | 类型       | 说明               | 优先级  |
| ------------- | -------- | ---------------- | ---- |
| `services`    | Object   | 服务定义集合           | 必须   |
| `image`       | String   | OCI 镜像地址及标签      | 必须   |
| `enabled`     | Boolean  | 是否启用服务，默认 `true` | 必须   |
| `volumes`     | String[] | 宿主机与容器目录绑定       | 必须支持 |
| `environment` | Object   | 启动时注入环境变量        | 首版   |
| `command`     | String[] | 可选启动命令覆盖         | 后续   |
| `working_dir` | String   | 可选工作目录覆盖         | 后续   |
| `depends_on`  | String[] | 服务启动顺序依赖         | 后续   |
| `healthcheck` | Object   | 服务健康检查规则         | 后续   |

### 4.3 路径解析规则

所有相对路径均相对于 YAML 配置文件所在目录解析。

例如：

```yaml
volumes:
  - ./data/service:/app/data
```

如果配置文件位于：

```text
~/termux-containers/containers.yaml
```

则宿主机路径解析为：

```text
~/termux-containers/data/service
```

不得依赖 CLI 执行时的当前工作目录。

### 4.4 绑定目录初始化

程序应当在容器启动前检查所有宿主机绑定路径。

处理规则：

1. 如果声明的是目录且目录不存在，自动创建。
2. 如果声明的是文件且文件不存在，应当支持显式初始化规则，或报告清晰的错误。
3. 如果路径类型与声明不一致，终止该服务的应用操作。
4. 不应隐式覆盖用户已有文件。
5. 不应自动删除已经存在的宿主机数据。

首版可以优先支持目录绑定，文件初始化作为后续扩展。

### 4.5 配置校验

应用之前必须验证配置。

至少检查：

- YAML 语法是否合法。
- 服务名称是否合法且不重复。
- 镜像地址是否存在。
- 字段类型是否正确。
- 目录绑定格式是否正确。
- 宿主路径是否可以访问。
- 是否存在明显的端口或启动配置冲突（可检测的情况下）。

配置无效时，不应执行破坏性操作。

---

## 5. CLI 功能设计

建议使用统一入口：

```bash
termux-containers <command>
```

### 5.1 `init` — 环境初始化

```bash
termux-containers init
```

负责初始化 Termux 运行环境，包括：

- 检查是否运行在 Termux 中。
- 检查和安装必要的系统依赖。
- 安装或检查 PRoot-Distro。
- 创建项目工作目录。
- 初始化默认配置文件（不存在时）。
- 配置 Termux Session 自启动入口。
- 验证运行环境是否可用。

初始化操作必须支持重复执行，不覆盖已有用户配置。

### 5.2 `start` — 启动已配置服务

```bash
termux-containers start
```

根据 YAML 配置启动所有 `enabled: true` 的服务。

要求：

- 已经运行的服务不重复启动。
- 已安装但未运行的服务直接启动。
- 未安装的服务不在普通自启动流程中进行网络下载。
- 单个服务启动失败不应阻止其他独立服务启动。
- 避免并发执行导致重复启动。

同时支持指定服务：

```bash
termux-containers start cli-proxy
```

### 5.3 `stop` — 停止服务

```bash
termux-containers stop
termux-containers stop cli-proxy
```

停止由当前项目管理的服务。

不删除容器文件系统，也不删除绑定数据。

### 5.4 `status` — 查看状态

```bash
termux-containers status
```

输出配置中的服务及其实际状态。

例如：

```text
SERVICE       IMAGE                  STATUS
cli-proxy     cli-proxy:latest       Running
note-sync     note-sync:latest       Stopped
```

实际信息通过 PRoot-Distro 查询，不依赖自建状态数据库。

### 5.5 `apply` — 应用配置

```bash
termux-containers apply
```

将当前容器状态调整至 YAML 配置描述的期望状态。

要求：

- 安装缺失的容器。
- 启动应该运行但未运行的容器。
- 停止被禁用的容器。
- 在必要时重新部署变更的容器。
- 避免修改无关容器。
- 保留宿主机绑定数据。
- 对失败操作提供明确错误信息。

**首版不主动检查远端镜像是否更新。**

当用户显式修改 `image` 地址或版本标签时，程序应当根据变更重新部署对应容器。

后续可以增加：

```bash
termux-containers apply --pull
```

用于主动检查并获取远端的新镜像。

### 5.6 配置文件指定

所有需要读取配置的命令应当支持：

```bash
termux-containers -f ./containers.yaml apply
```

默认读取项目工作目录中的 `containers.yaml`。

---

## 6. 配置应用与变更处理

### 6.1 期望行为

| 情况                   | 操作               |
| -------------------- | ---------------- |
| 容器尚未安装               | 安装并启动            |
| 容器已安装但未运行            | 启动               |
| 容器正在运行且配置一致          | 不操作              |
| 环境变量发生变化             | 重新启动             |
| 绑定目录发生变化             | 重新启动             |
| 镜像地址或版本变化            | 重新部署             |
| `enabled` 改为 `false` | 停止容器             |
| 服务从配置文件中删除           | 不自动删除数据，后续提供清理机制 |


---

## 7. Termux Session 自启动

### 7.1 目标

每次创建 Termux Session 时，自动确保配置文件中的所有已安装且启用的容器正在运行。

### 7.2 实现方式

通过 Termux Shell 启动配置触发：

```bash
termux-containers start
```

需要兼容用户当前使用的 Shell，例如 Bash 或 Zsh。

### 7.3 约束

- 不重复启动已经运行的容器。
- 不自动更新镜像。
- 不在启动 Session 时进行大规模下载。
- 不阻塞正常 Shell 交互。
- 避免多个 Session 同时执行造成竞争。
- 启动失败不应使 Termux Shell 无法使用。

---

## 8. 可选 Web UI

Web UI 不属于首版必需功能，但系统设计应当支持后续添加。Web UI 主体内容是一个轻量级 YAML 配置编辑器

核心功能：

1. 读取当前 YAML 配置。
2. 编辑配置内容。
3. 验证配置。
4. 保存配置。
5. 确认并执行 `apply`。
6. 查看基础容器运行状态。

---

## 9. 技术方案

### 9.1 建议技术栈

| 模块          | 技术                 |
| ----------- | ------------------ |
| 核心程序        | Python         |
| 配置格式        | YAML               |
| 容器管理        | PRoot-Distro CLI   |
| Web UI（后续）  | React              |
| Web API（后续） | 轻量 HTTP 服务         |
