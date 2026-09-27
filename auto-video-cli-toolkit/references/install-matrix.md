# 分系统安装矩阵

目标：在任意系统上，把工具装到**最不容易出错、最不需要管理员权限、最容易升级**的位置。

## 一、什么叫「最佳安装位置」

按优先级排序，前一条可行就不用后一条：

1. **用户级包管理器** —— 不需要管理员密码，装到用户目录，卸载升级都干净
2. **系统包管理器** —— 需要一次授权，但后续由系统统一升级
3. **官方静态二进制** —— 放到用户级 bin 目录，手动升级
4. **绝不做的事** —— `sudo pip install`（会污染系统 Python）、往 `/usr/bin` 手动拷贝文件、下载来路不明的「破解版」

## 二、各系统默认落点

| 系统 | 推荐通道 | 安装落点 | 是否需要管理员 |
|---|---|---|---|
| macOS（Intel） | Homebrew | `/usr/local/bin` | 否 |
| macOS（Apple Silicon） | Homebrew | `/opt/homebrew/bin` | 否 |
| Debian / Ubuntu | apt | `/usr/bin` | 是 |
| Fedora / RHEL | dnf | `/usr/bin` | 是 |
| Arch / Manjaro | pacman | `/usr/bin` | 是 |
| openSUSE | zypper | `/usr/bin` | 是 |
| Alpine | apk | `/usr/bin` | 是 |
| Windows | Scoop | `%USERPROFILE%\scoop\shims` | 否 |
| Windows | winget | `%LOCALAPPDATA%\Microsoft\WinGet\Links` | 多数否 |
| 任意系统的 Python 工具 | pip --user | Linux `~/.local/bin`<br>macOS `~/Library/Python/3.x/bin`<br>Windows `%APPDATA%\Python\Python3x\Scripts` | 否 |

Homebrew 在 Apple Silicon 上装到 `/opt/homebrew` 而非 `/usr/local`，这是最常见的「装完了却提示 command not found」原因。修复方式见第四节。

## 三、逐平台安装步骤

先运行环境探测确定缺什么：

```bash
python3 scripts/detect_env.py --human
```

### macOS

```bash
# 若尚未安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装全部推荐工具
brew install ffmpeg yt-dlp auto-editor mkvtoolnix media-info gifski exiftool sox
```

不需要 `sudo`。Homebrew 会自行处理依赖与 PATH。

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y ffmpeg yt-dlp mkvtoolnix mediainfo sox \
                    libimage-exiftool-perl tesseract-ocr tesseract-ocr-chi-sim
python3 -m pip install --user -U auto-editor
```

### Fedora / RHEL

Fedora 官方源里的包叫 **`ffmpeg-free`**，不是 `ffmpeg`，且刻意去掉了部分受专利限制的编码器。要求完整功能时先启用 RPM Fusion：

```bash
# 官方源版本（够用，但编码器不全）
sudo dnf install -y ffmpeg-free yt-dlp mkvtoolnix mediainfo sox tesseract tesseract-langpack-chi_sim

# 需要完整编码器时启用 RPM Fusion
sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install -y ffmpeg

python3 -m pip install --user -U auto-editor
```

### Arch / Manjaro

```bash
sudo pacman -S --noconfirm ffmpeg yt-dlp mkvtoolnix-cli mediainfo sox \
                               perl-image-exiftool tesseract tesseract-data-chi_sim
python3 -m pip install --user -U auto-editor
```

### Alpine

```bash
sudo apk add ffmpeg yt-dlp mkvtoolnix mediainfo sox exiftool tesseract-ocr
python3 -m pip install --user -U auto-editor yt-dlp
```

### Windows

优先级：**Scoop（纯用户级，无需管理员）> winget（系统自带）> Chocolatey（需管理员）**。

```powershell
# 方案 A：Scoop，推荐在受管控的公司电脑上使用
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
scoop install main/ffmpeg yt-dlp auto-editor mkvtoolnix gifski mediainfo exiftool sox

# 方案 B：winget，Windows 10 1709+ 自带，无需预先安装
winget install --id Gyan.FFmpeg -e
winget install --id yt-dlp.yt-dlp -e
```

装完必须**新开一个终端窗口**：当前窗口的 PATH 不会自动刷新。

## 四、没有包管理器 / 没有管理员权限时

### 通用兜底：用户级二进制

适用于 Linux 服务器、容器、受管控的办公电脑。

```bash
mkdir -p ~/.local/bin
# yt-dlp
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp
chmod +x ~/.local/bin/yt-dlp
# ffmpeg 静态构建（下载后解压，把里面的 ffmpeg/ffprobe 拷进 ~/.local/bin）
```

### PATH 配置

```bash
# macOS / Linux：写进 ~/.zshrc 或 ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
```

确认落点确实生效：

```bash
echo $PATH | tr ':' '\n' | grep -q "$HOME/.local/bin" && echo "PATH 正常" || echo "需要配置 PATH"
```

Windows 用户级 PATH 请用 PowerShell 设置，**不要用 `setx`** —— `setx` 会在 1024 字符处静默截断 PATH，破坏其它软件：

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\ffmpeg\bin",
  "User"
)
```

### macOS 上 Homebrew 命令找不到

Apple Silicon 机器需要显式载入 Homebrew 环境，把它写进 `~/.zprofile`：

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

## 五、安装后必做的验证

```bash
python3 scripts/detect_env.py --human   # 工具状态应全部变为「已装」
ffmpeg -version | head -1                # 能打印版本即成功
ffprobe -version | head -1
```

若某条仍显示「未装」，按顺序检查：PATH 是否刷新（重开终端）→ 落点是否在 PATH 中 → 二进制是否有可执行权限。

## 六、升级与卸载

| 通道 | 升级 | 卸载 |
|---|---|---|
| brew | `brew upgrade <包名>` | `brew uninstall <包名>` |
| apt | `sudo apt update && sudo apt upgrade` | `sudo apt remove <包名>` |
| dnf | `sudo dnf upgrade` | `sudo dnf remove <包名>` |
| pacman | `sudo pacman -Syu` | `sudo pacman -R <包名>` |
| scoop | `scoop update <包名>` | `scoop uninstall <包名>` |
| winget | `winget upgrade` | `winget uninstall <包名>` |
| pip --user | `python3 -m pip install --user -U <包名>` | `python3 -m pip uninstall <包名>` |

## 七、容易踩的坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 装完提示 command not found | 当前终端未刷新 PATH | 新开终端窗口；仍未解决则检查落点是否在 PATH |
| Apple Silicon 上找不到 brew 装的工具 | Homebrew 装在 `/opt/homebrew` | 执行 `eval "$(/opt/homebrew/bin/brew shellenv)"` |
| `sudo pip install` 后系统 Python 报错 | 系统 Python 被判为 externally-managed | 改用 `pip install --user`，不要动系统 Python |
| Fedora 装了 ffmpeg 却没有 x264 | `ffmpeg-free` 移除了专利编码器 | 启用 RPM Fusion 后装完整版 ffmpeg |
| Windows 装完 ffmpeg 打不开 | ffmpeg 是命令行工具，双击必然闪退 | 在终端里运行 `ffmpeg -version` |
| winget 装了但旧终端找不到 | PATH 对新会话生效 | 新开终端 |
| 装了 ffmpeg 仍无法烧字幕 | 该构建未编译 libass | 用 `detect_env.py` 查限制，必要时换官方完整构建 |
