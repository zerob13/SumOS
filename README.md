# SumOS

A small, agent-first Linux live system, powered by [Dim](https://github.com/arcships/dim).

SumOS 的发行版配置与集成代码使用 MIT；镜像内的 Linux、Debian 软件包、Dim 和第三方组件各自保留原许可证。SumOS 是独立项目，不是 Debian 或 Dim 官方发行版。

## 首版范围

- Debian 13 stable / amd64，BIOS + UEFI hybrid Live ISO。
- Openbox + X11 + tint2 + PCManFM + LXTerminal，无完整桌面元包、Firefox 或 Electron 外壳。
- 固定版本的官方 account-enabled Dim 原生包，作为当前桌面用户的 systemd 服务启动。
- 原生 Tk 欢迎页自动申请 OAuth 设备码，显示二维码、验证码、登录进度，支持中国/全球服务、重试、离线跳过和暂停。
- Dim 官方仓库品牌图用于 GRUB、Plymouth 和壁纸，保留出处。
- Bash/Zsh 基础补全、Neovim、tmux、ripgrep、fd、fzf；默认不加载 LazyVim、语言服务器或本地模型。
- zram，目标硬件 4GB 内存；CI 以 **4 GiB** 虚拟机验证桌面和 Dim RPC，空闲已用内存预算 900 MiB。真实 Chrome/网页/Agent 工作负载需实机测量，不能由此保证任意负载流畅。

**当前是 Live 原型，不含磁盘安装器、Secure Boot 支持或预装闭源固件。** 默认只使用 Debian main。部分 Wi-Fi、显卡需要额外固件；首轮建议以有线网络或受支持的虚拟网卡测试。Live 内的账号和文件默认随关机丢失。可在了解 Debian Live 的加密持久化配置后自行启用持久化；不要在公开重打包的镜像中保存登录凭据。

Google Chrome 不随公共 ISO 再分发。在欢迎页接受 Google 条款后，由签名 APT 仓库联网安装并保留自动更新源；需要管理员授权。离线时 Dim UI 与系统可启动，联网登录和推理不可用。安装 Chrome 会占用 Live overlay 和额外内存。

## 本地构建

在 amd64 Linux **完整虚拟机或 rootful Docker 主机**上执行，预留至少 30GB 可用磁盘、8GB RAM。构建机需求高于运行镜像的 4GB 目标。rootless 容器或不允许 mount 的沙箱不能构建 Live ISO。

```sh
docker build -t sumos-builder .
docker run --rm --privileged -v "$PWD:/repo" sumos-builder
sudo chown -R "$(id -u):$(id -g)" dist build
```

不要在 `live/` 中执行 `lb build`。脚本在新的 `build/iso/` 工作目录操作，生成 `dist/sumos-amd64.iso`、Debian 对应源码分卷、Dim 源码、SumOS 源码、许可证、软件包清单和 `SHA256SUMS`。缺少对应源码、源码版本不匹配、`.dsc` 文件校验失败或 ISO 大于 1900 MiB 时拒绝打包。

重建前先在构建器中运行 `cd build/iso && lb clean --purge`，确认没有遗留挂载，再清理 `build/iso` 和 `dist`。不要直接删除仍挂载着 `/proc`、`/sys` 或 `/dev` 的构建树。

版本与校验值在 [versions.json](versions.json)。Dim 通过 SHA-512 校验原生归档，逐文件校验上游清单，并验证 account-enabled 标志；不执行 npm 安装脚本、不从可变的 `latest` 下载。Debian stable 更新由 APT 签名验证，具体版本记录在每次构建的软件包清单中；目前不声称跨日期逐字节可复现。

## 开机使用

Live 用户名为 `sumos`，由 Debian live-config 自动登录。Live 权限遵循 Debian Live 默认设置，包括可能允许免密码 sudo；这是便携测试环境，不能当作已加固的多用户系统。

1. 启动后欢迎页自动连接 Dim，联网时展示设备登录二维码。用手机扫描，并按页面提示输入单独显示的验证码。
2. 授权后选择 **Open agent**，在 Dim 中选模型并发送任务。模型调用仍取决于账户、配额和网络。
3. 不登录也可以打开桌面、终端和文件管理器。需要 API key 时用 Dim 自身的配置入口；不要把凭据写进 ISO。

| 快捷键 | 操作 |
| --- | --- |
| Super+Enter | 打开 / 恢复 Agent |
| Super+Esc | 停止 Dim systemd 服务及其进程组 |
| Super+Space | 打开欢迎页 / 登录 / Chrome 安装 |
| Super+T | 终端 |
| Super+E | 文件管理器 |
| Alt+Tab / Alt+F4 | 切换 / 关闭窗口 |

```sh
systemctl --user status sumos-dim
journalctl --user -u sumos-dim
sumos-pause
sumos-agent
```

`dim` 命令固定使用 `~/.dimcode`，服务、CLI 和欢迎页共享 `~/.dimcode/rust/daemon.sock`。没有公网 RPC 端口。不要同时启动另一个同目录的上游守护进程。桌面会话启动服务，不开启 linger；退出用户会话时应结束用户服务。

Agent 以普通用户运行，保留 Dim 的工具审批。X11、同用户文件和 shell 本身不是安全隔离边界；暂停按钮也是操作控制，不是防恶意代码的安全机制。不要用 `sudo dim`，不要把 Live 默认权限用于生产密钥保护。

## 验证

Debian 上安装 `python3-tk python3-pil python3-pil.imagetk python3-qrcode xvfb xauth shellcheck live-build` 后：

```sh
python3 scripts/fetch-dim.py --prefix build/staging
bash scripts/check.sh
DIM_BINARY="$PWD/build/staging/opt/dim/bin/dimcode" \
  xvfb-run -a python3 -m unittest discover -s tests -v
python3 scripts/prepare.py build/config-check
```

`prepare.py` 的目标必须不存在。测试会实际启动锁定的 Dim 原生服务，验证 CLI/RPC 互通及设备登录能力；欢迎页流程使用本地协议服务模拟授权成功、过期、断网与取消，不使用真实账户。

构建 ISO 后安装 `qemu-system-x86 ovmf python3-pil`，执行：

```sh
python3 scripts/smoke-iso.py dist/sumos-amd64.iso --firmware bios
python3 scripts/smoke-iso.py dist/sumos-amd64.iso --firmware uefi
```

测试直接启动最终 ISO，等待真实 Openbox、tint2 和 Dim RPC 就绪，记录内存和桌面截图；超时或超过预算时失败。它不覆盖真实 OAuth 服务、模型响应、物理 GPU/Wi-Fi、持久化或磁盘安装。

## CI 和 Release

[GitHub Actions](.github/workflows/iso.yml)：PR 做静态检查和原生集成测试；推送 master 或手动触发后构建 ISO、对应源码，并执行 BIOS/UEFI 4 GiB 启动检查。全部通过后保留 14 天构建产物。

推送 `v*` 标签会在以上检查通过后自动创建 **GitHub prerelease**，上传同一次构建的 ISO、全部源码分卷、许可证、清单、截图、日志和校验值。使用仓库自带的 `GITHUB_TOKEN`，无额外 OAuth client ID 或账号 secret。初版不自动标记为稳定版。

```sh
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

只有实际运行 CI 并检查产物后，才能称为已验证的 ISO Release。源码分卷必须与 ISO 一起保留和分发，见 [许可与源码交付](docs/LICENSING.md)。

后续开发与验收路线见 [ROADMAP](docs/ROADMAP.md)。
