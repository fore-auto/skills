#!/usr/bin/env python3
"""auto-video-cli-toolkit · 环境探测器

探测当前机器的操作系统、包管理器、视频工具链安装状态，并据此生成
「按平台最佳位置安装」的可执行命令清单。

设计约束：
  - 仅使用 Python 标准库，不依赖任何第三方包
  - 跨平台：macOS / Linux / Windows
  - 全部探测带超时保护，单个工具卡死不影响整体
  - 只做只读探测，不安装、不修改任何文件

用法：
    python3 detect_env.py               # 输出 JSON（供程序消费）
    python3 detect_env.py --human       # 输出人类可读报告
    python3 detect_env.py --plan        # 只输出待安装工具的安装命令
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 12

# ---------------------------------------------------------------- 工具清单

TOOLS = [
    {"cmd": "ffmpeg", "tier": "core", "role": "转码 / 剪辑 / 滤镜引擎"},
    {"cmd": "ffprobe", "tier": "core", "role": "媒体信息探测"},
    {"cmd": "yt-dlp", "tier": "rec", "role": "从各平台下载视频"},
    {"cmd": "auto-editor", "tier": "rec", "role": "按静音自动粗剪"},
    {"cmd": "mkvmerge", "tier": "rec", "role": "无损多轨封装 / 拆分"},
    {"cmd": "mediainfo", "tier": "rec", "role": "媒体信息详查"},
    {"cmd": "gifski", "tier": "opt", "role": "高质量 GIF 导出"},
    {"cmd": "exiftool", "tier": "opt", "role": "元数据读写"},
    {"cmd": "sox", "tier": "opt", "role": "音频处理 / 格式转换"},
    {"cmd": "whisper-cli", "tier": "opt", "role": "语音转字幕"},
    {"cmd": "tesseract", "tier": "opt", "role": "硬字幕 OCR 识别"},
]

VERSION_ARGS = {
    "ffmpeg": ["-version"],
    "ffprobe": ["-version"],
    "yt-dlp": ["--version"],
    "mkvmerge": ["--version"],
    "auto-editor": ["--version"],
    "mediainfo": ["--Version"],
    "gifski": ["--version"],
    "exiftool": ["-ver"],
    "sox": ["--version"],
    "whisper-cli": ["--version"],
    "tesseract": ["--version"],
}

# 每个工具在各平台的首选安装命令。linux 细分到发行版家族。
# needs_admin 标注该命令是否需要管理员权限，供「最佳位置」决策使用。
INSTALL_MATRIX = {
    "ffmpeg": {
        "mac": ("brew install ffmpeg", False),
        "win": ("scoop install main/ffmpeg", False),
        "linux-debian": ("sudo apt install -y ffmpeg", True),
        "linux-fedora": ("sudo dnf install -y ffmpeg-free", True),
        "linux-arch": ("sudo pacman -S --noconfirm ffmpeg", True),
        "linux-suse": ("sudo zypper install -y ffmpeg", True),
        "linux-alpine": ("sudo apk add ffmpeg", True),
        "linux": ("sudo apt install -y ffmpeg", True),
    },
    "ffprobe": {"_inherit": "ffmpeg"},
    "yt-dlp": {
        "mac": ("brew install yt-dlp", False),
        "win": ("scoop install yt-dlp", False),
        "linux-debian": ("sudo apt install -y yt-dlp", True),
        "linux-fedora": ("sudo dnf install -y yt-dlp", True),
        "linux-arch": ("sudo pacman -S --noconfirm yt-dlp", True),
        "linux-suse": ("sudo zypper install -y yt-dlp", True),
        "linux-alpine": ("sudo apk add yt-dlp", True),
        "linux": ("sudo apt install -y yt-dlp", True),
        "fallback": ("python3 -m pip install --user -U yt-dlp", False),
    },
    "auto-editor": {
        "mac": ("brew install auto-editor", False),
        "win": ("scoop install auto-editor", False),
        "linux": ("python3 -m pip install --user -U auto-editor", False),
    },
    "mkvmerge": {
        "mac": ("brew install mkvtoolnix", False),
        "win": ("scoop install mkvtoolnix", False),
        "linux-debian": ("sudo apt install -y mkvtoolnix", True),
        "linux-fedora": ("sudo dnf install -y mkvtoolnix", True),
        "linux-arch": ("sudo pacman -S --noconfirm mkvtoolnix-cli", True),
        "linux-suse": ("sudo zypper install -y mkvtoolnix", True),
        "linux-alpine": ("sudo apk add mkvtoolnix", True),
        "linux": ("sudo apt install -y mkvtoolnix", True),
    },
    "mediainfo": {
        "mac": ("brew install media-info", False),
        "win": ("scoop install mediainfo", False),
        "linux-debian": ("sudo apt install -y mediainfo", True),
        "linux-fedora": ("sudo dnf install -y mediainfo", True),
        "linux-arch": ("sudo pacman -S --noconfirm mediainfo", True),
        "linux-suse": ("sudo zypper install -y mediainfo", True),
        "linux-alpine": ("sudo apk add mediainfo", True),
        "linux": ("sudo apt install -y mediainfo", True),
    },
    "gifski": {
        "mac": ("brew install gifski", False),
        "win": ("scoop install gifski", False),
        "linux": None,
    },
    "exiftool": {
        "mac": ("brew install exiftool", False),
        "win": ("scoop install exiftool", False),
        "linux-debian": ("sudo apt install -y libimage-exiftool-perl", True),
        "linux-fedora": ("sudo dnf install -y perl-Image-ExifTool", True),
        "linux-arch": ("sudo pacman -S --noconfirm perl-image-exiftool", True),
        "linux-suse": ("sudo zypper install -y exiftool", True),
        "linux-alpine": ("sudo apk add exiftool", True),
        "linux": ("sudo apt install -y libimage-exiftool-perl", True),
    },
    "sox": {
        "mac": ("brew install sox", False),
        "win": ("scoop install sox", False),
        "linux-debian": ("sudo apt install -y sox", True),
        "linux-fedora": ("sudo dnf install -y sox", True),
        "linux-arch": ("sudo pacman -S --noconfirm sox", True),
        "linux-suse": ("sudo zypper install -y sox", True),
        "linux-alpine": ("sudo apk add sox", True),
        "linux": ("sudo apt install -y sox", True),
    },
    "whisper-cli": {
        "mac": ("brew install whisper-cpp", False),
        "win": None,
        "linux-debian": ("sudo apt install -y whisper.cpp", True),
        "linux": None,
        "note": "另需下载 ggml 模型文件才能使用",
    },
    "tesseract": {
        "mac": ("brew install tesseract tesseract-lang", False),
        "win": ("scoop install tesseract", False),
        "linux-debian": ("sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim", True),
        "linux-fedora": ("sudo dnf install -y tesseract tesseract-langpack-chi_sim", True),
        "linux-arch": ("sudo pacman -S --noconfirm tesseract tesseract-data-chi_sim", True),
        "linux": ("sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim", True),
    },
}

# ffmpeg 编译能力检查项：缺失会导致对应功能不可用
FFMPEG_FEATURE_CHECKS = {
    "filters": {
        "subtitles": "硬字幕烧录（读取字幕文件并压进画面）",
        "ass": "ASS 特效字幕烧录",
        "drawtext": "在画面上叠加文字",
        "overlay": "叠加图片水印 / 画中画",
        "delogo": "擦除画面固定区域（去水印 / 去台标）",
        "loudnorm": "音量响度标准化",
        "xfade": "两段视频之间的转场",
        "minterpolate": "运动补偿补帧",
        "deshake": "画面防抖",
    },
    "encoders": {
        "libx264": "H.264 软件编码（兼容性最好）",
        "libx265": "H.265 软件编码（体积更小）",
        "libsvtav1": "AV1 软件编码（体积最小，编码慢）",
        "h264_videotoolbox": "H.264 硬件编码（macOS）",
        "hevc_videotoolbox": "H.265 硬件编码（macOS）",
        "h264_nvenc": "H.264 硬件编码（NVIDIA 显卡）",
        "h264_qsv": "H.264 硬件编码（Intel 核显）",
    },
    "protocols": {
        "rtmp": "直播推流到各平台",
        "srt": "SRT 低延迟推流 / 收流",
    },
}


# ---------------------------------------------------------------- 基础工具函数


def run(cmd: list[str], timeout: int = TIMEOUT) -> str:
    """执行命令并返回 stdout+stderr，失败返回空串。绝不抛异常。"""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception:
        return ""


def run_stdout(cmd: list[str], timeout: int = TIMEOUT) -> str:
    """只返回 stdout。

    ffmpeg 把 banner 和版本信息写到 stderr，若与 stdout 合流会污染
    -filters / -encoders / -hwaccels 这类结构化输出，故单独提供本函数。
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return proc.stdout or ""
    except Exception:
        return ""


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def is_admin() -> bool:
    """判断当前会话是否具备管理员 / root 权限。"""
    try:
        if os.name == "nt":
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def detect_platform() -> dict:
    system = platform.system().lower()
    arch = platform.machine() or "unknown"

    if system == "darwin":
        os_name, normalized = "macos", "mac"
        distro = None
        ver = platform.mac_ver()[0]
    elif system == "windows":
        os_name, normalized = "windows", "win"
        distro = None
        ver = platform.version()
    else:
        os_name, normalized = "linux", "linux"
        distro, ver = None, platform.release()
        try:
            rel = Path("/etc/os-release").read_text(errors="replace")
            fields = dict(
                line.split("=", 1)
                for line in rel.splitlines()
                if "=" in line and not line.startswith("#")
            )
            distro = (fields.get("ID") or "").strip('"')
            ver = (fields.get("VERSION_ID") or ver).strip('"')
            id_like = (fields.get("ID_LIKE") or "").strip('"')
            family_source = f"{distro} {id_like}".lower()
            family_map = [
                ("arch", "linux-arch"),
                ("fedora", "linux-fedora"),
                ("rhel", "linux-fedora"),
                ("debian", "linux-debian"),
                ("ubuntu", "linux-debian"),
                ("suse", "linux-suse"),
                ("alpine", "linux-alpine"),
            ]
            for key, family in family_map:
                if key in family_source:
                    normalized = family
                    break
        except Exception:
            pass

    return {
        "os": os_name,
        "normalized": normalized,
        "arch": arch,
        "distro": distro,
        "version": ver,
        "is_admin": is_admin(),
    }


def detect_package_managers(plat: dict) -> dict:
    """探测可用的包管理器，并按「免管理员优先」排序给出推荐。"""
    candidates = []
    if plat["normalized"] == "mac":
        candidates = [("brew", False)]
    elif plat["normalized"] == "win":
        candidates = [("scoop", False), ("winget", False), ("choco", True)]
    elif plat["normalized"].startswith("linux-"):
        candidates = [
            ("apt", True),
            ("dnf", True),
            ("pacman", True),
            ("zypper", True),
            ("apk", True),
        ]
    candidates += [("pip", False), ("npm", False), ("cargo", False)]

    available = []
    seen = set()
    for name, needs_admin in candidates:
        if name in seen:
            continue
        seen.add(name)
        for probe in ([name, f"{name}3"] if name == "pip" else [name]):
            path = shutil.which(probe)
            if path:
                if probe != name:
                    name = probe
                available.append(
                    {"name": name, "path": path, "needs_admin": needs_admin}
                )
                break

    recommended = None
    for pm in available:
        if pm["needs_admin"] is False or not plat["is_admin"]:
            recommended = pm["name"]
            break
    if recommended is None and available:
        recommended = available[0]["name"]

    return {"available": available, "recommended": recommended}


def user_bin_dir(plat: dict) -> dict:
    """确定用户级可执行文件目录，并检查是否已在 PATH 中。"""
    if plat["normalized"] == "win":
        home = Path.home()
        scoop_shims = home / "scoop" / "shims"
        target = scoop_shims if scoop_shims.exists() else home / ".local" / "bin"
    else:
        target = Path.home() / ".local" / "bin"

    in_path = str(target) in os.environ.get("PATH", "").split(os.pathsep)
    return {"path": str(target), "exists": target.exists(), "in_path": in_path}


def check_ffmpeg(path: str) -> dict:
    """探测 ffmpeg 的编译能力，并推导出功能限制。"""
    info = {
        "installed": True,
        "path": path,
        "filters": {},
        "encoders": {},
        "protocols": {},
        "hwaccels": [],
        "limitations": [],
    }

    build = run([path, "-hide_banner", "-buildconf"])
    flag_src = build.lower()
    info["build_flags"] = sorted(
        {
            token.strip()
            for token in flag_src.replace("\n", " ").split()
            if token.strip().startswith("--enable-")
        }
    )

    filters_out = run_stdout([path, "-hide_banner", "-filters"])
    for name, desc in FFMPEG_FEATURE_CHECKS["filters"].items():
        info["filters"][name] = {
            "available": f" {name} " in filters_out,
            "desc": desc,
        }

    enc_out = run_stdout([path, "-hide_banner", "-encoders"])
    for name, desc in FFMPEG_FEATURE_CHECKS["encoders"].items():
        info["encoders"][name] = {"available": name in enc_out, "desc": desc}

    proto_out = run_stdout([path, "-hide_banner", "-protocols"])
    for name, desc in FFMPEG_FEATURE_CHECKS["protocols"].items():
        has = f"\n  {name}\n" in "\n" + proto_out + "\n"
        info["protocols"][name] = {"available": has, "desc": desc}

    hw = run_stdout([path, "-hide_banner", "-hwaccels"])
    info["hwaccels"] = [
        line.strip()
        for line in hw.splitlines()
        if line.strip() and "acceleration" not in line.lower()
    ]

    # 推导限制说明
    missing_filters = [
        n for n, v in info["filters"].items() if not v["available"]
    ]
    if "subtitles" in missing_filters or "ass" in missing_filters:
        info["limitations"].append(
            "当前 ffmpeg 未编译 libass：无法把字幕烧录进画面（内挂软字幕仍可用）"
        )
    if "drawtext" in missing_filters:
        info["limitations"].append(
            "当前 ffmpeg 未编译 freetype：无法在画面上叠加文字"
        )
    if not info["protocols"]["srt"]["available"]:
        info["limitations"].append("当前 ffmpeg 未编译 libsrt：无法使用 SRT 协议推流")
    has_hw_encoder = any(
        info["encoders"][k]["available"]
        for k in ("h264_videotoolbox", "hevc_videotoolbox", "h264_nvenc", "h264_qsv")
    )
    if not has_hw_encoder:
        info["limitations"].append(
            "未检测到可用硬件编码器：长时间转码只能走 CPU，速度较慢"
        )

    return info


def probe_tools() -> list[dict]:
    results = []
    for tool in TOOLS:
        cmd = tool["cmd"]
        path = shutil.which(cmd)
        entry = dict(tool)
        entry["installed"] = bool(path)
        entry["path"] = path or None
        entry["version"] = None
        if path:
            raw = run([path] + VERSION_ARGS.get(cmd, ["--version"]))
            line = first_line(raw)
            entry["version"] = line[:120] if line else "未知"
        results.append(entry)
    return results


def build_install_plan(plat: dict, tools: list[dict], pms: dict) -> list[dict]:
    """为缺失的工具生成安装命令，按平台选择最佳通道。"""
    plan = []
    available_pm_names = {pm["name"] for pm in pms["available"]}

    for tool in tools:
        if tool["installed"] or tool["tier"] == "core":
            continue
        rules = INSTALL_MATRIX.get(tool["cmd"], {})
        if not rules:
            continue

        if "_inherit" in rules:
            rules = INSTALL_MATRIX.get(rules["_inherit"], {})

        normalized = plat["normalized"]
        choice = rules.get(normalized)
        if choice is None and normalized.startswith("linux-"):
            choice = rules.get("linux")

        command, needs_admin = (None, False)
        channel = None

        if choice:
            command, needs_admin = choice
            channel = normalized

        # 包管理器缺失时，回退到 pip / 用户级方案
        if command:
            pm_name = command.split()[0]
            if pm_name == "sudo":
                pm_name = command.split()[1]
            if pm_name not in available_pm_names and pm_name in ("brew", "scoop", "winget", "choco"):
                fb = rules.get("fallback")
                if fb:
                    command, needs_admin = fb
                    channel = "fallback"

        if not command:
            fb = rules.get("fallback")
            if fb:
                command, needs_admin = fb
                channel = "fallback"
            else:
                command, needs_admin, channel = None, False, "manual"

        plan.append(
            {
                "tool": tool["cmd"],
                "tier": tool["tier"],
                "role": tool["role"],
                "channel": channel,
                "command": command,
                "needs_admin": needs_admin,
                "note": rules.get("note"),
            }
        )
    return plan


def disk_free_gb() -> float | None:
    try:
        import shutil as _sh

        return round(_sh.disk_usage(str(Path.home())).free / (1024**3), 1)
    except Exception:
        return None


# ---------------------------------------------------------------- 输出


def collect() -> dict:
    plat = detect_platform()
    pms = detect_package_managers(plat)
    tools = probe_tools()

    ffmpeg_path = next((t["path"] for t in tools if t["cmd"] == "ffmpeg"), None)
    ffmpeg = check_ffmpeg(ffmpeg_path) if ffmpeg_path else {"installed": False}

    gaps = {
        "core": [t["cmd"] for t in tools if not t["installed"] and t["tier"] == "core"],
        "rec": [t["cmd"] for t in tools if not t["installed"] and t["tier"] == "rec"],
        "opt": [t["cmd"] for t in tools if not t["installed"] and t["tier"] == "opt"],
    }

    return {
        "platform": plat,
        "package_managers": pms,
        "user_bin": user_bin_dir(plat),
        "tools": tools,
        "gaps": gaps,
        "ffmpeg": ffmpeg,
        "install_plan": build_install_plan(plat, tools, pms),
        "disk_free_gb": disk_free_gb(),
    }


def render_human(env: dict) -> str:
    p = env["platform"]
    out = []
    out.append("=" * 62)
    out.append("视频工具环境探测报告")
    out.append("=" * 62)
    out.append(
        f"系统      {p['os']} {p['version']} / {p['arch']}"
        + (f"  ({p['distro']})" if p.get("distro") else "")
    )
    out.append(f"权限      {'管理员' if p['is_admin'] else '普通用户'}")
    out.append(
        "包管理器  "
        + (", ".join(pm["name"] for pm in env["package_managers"]["available"]) or "无")
        + f"   推荐: {env['package_managers']['recommended']}"
    )
    ub = env["user_bin"]
    out.append(
        f"用户目录  {ub['path']}  ({'已存在' if ub['exists'] else '不存在'}"
        f", {'在 PATH 中' if ub['in_path'] else '不在 PATH 中'})"
    )
    out.append(f"磁盘可用  {env['disk_free_gb']} GB")
    out.append("")
    out.append("-" * 62)
    out.append("工具状态")
    out.append("-" * 62)
    for t in env["tools"]:
        mark = "已装" if t["installed"] else "未装"
        tier = {"core": "必需", "rec": "推荐", "opt": "可选"}[t["tier"]]
        ver = t["version"] or "-"
        out.append(f"[{mark}] {tier}  {t['cmd']:<14} {ver}")

    ff = env["ffmpeg"]
    out.append("")
    out.append("-" * 62)
    out.append("ffmpeg 能力")
    out.append("-" * 62)
    if ff.get("installed"):
        out.append("硬件加速  " + (", ".join(ff["hwaccels"]) or "无"))
        for group in ("filters", "encoders", "protocols"):
            for name, meta in ff[group].items():
                if meta["available"]:
                    out.append(f"  可用  {name:<22} {meta['desc']}")
        if ff["limitations"]:
            out.append("")
            for limit in ff["limitations"]:
                out.append(f"  限制  {limit}")
    else:
        out.append("  ffmpeg 未安装，无法探测能力")

    if env["install_plan"]:
        out.append("")
        out.append("-" * 62)
        out.append("待安装工具与推荐命令")
        out.append("-" * 62)
        for item in env["install_plan"]:
            admin = "需管理员" if item["needs_admin"] else "无需管理员"
            out.append(f"{item['tool']:<14} ({item['tier']}, {admin})")
            out.append(f"    {item['command'] or '需手动安装，见 references/install-matrix.md'}")
    else:
        out.append("")
        out.append("所有工具已就绪，无需安装。")
    out.append("=" * 62)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="视频工具环境探测器")
    parser.add_argument("--human", action="store_true", help="输出人类可读报告")
    parser.add_argument("--plan", action="store_true", help="只输出待安装命令")
    args = parser.parse_args()

    env = collect()

    if args.plan:
        for item in env["install_plan"]:
            if item["command"]:
                print(item["command"])
        return 0

    if args.human:
        print(render_human(env))
    else:
        print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
