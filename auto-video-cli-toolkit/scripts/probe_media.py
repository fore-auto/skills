#!/usr/bin/env python3
"""auto-video-cli-toolkit · 媒体参数探测与参数自动推导

面向「不懂技术细节的用户」：只要给出视频文件，本脚本自动读出不带技术
味的描述，并推导出可直接执行的 ffmpeg 命令（分辨率、码率、CRF、滤镜链
全部自动算好），无需用户填写任何参数。

设计约束：
  - 仅使用 Python 标准库（依赖外部的 ffprobe）
  - ffprobe 缺失时给出明确提示，不抛异常
  - 输出内容不覆盖源文件，输出名自动加后缀

用法：
    python3 probe_media.py <视频文件> [更多文件...]
    python3 probe_media.py <视频文件> --human
    python3 probe_media.py <视频文件> --target douyin
    python3 probe_media.py <视频文件> --outdir ./output
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 60

# 平台发布规格参考值。均为「通用建议区间」，非平台硬性规定；
# 平台要求变化时只需更新此表，无需改动其它逻辑。
PLATFORM_SPECS = {
    "douyin": {
        "label": "抖音",
        "width": 1080,
        "height": 1920,
        "vbr": "6M",
        "maxrate": "8M",
        "bufsize": "12M",
        "abr": "128k",
        "orientation": "portrait",
    },
    "shipinhao": {
        "label": "微信视频号",
        "width": 1080,
        "height": 1920,
        "vbr": "6M",
        "maxrate": "8M",
        "bufsize": "12M",
        "abr": "128k",
        "orientation": "portrait",
    },
    "xiaohongshu": {
        "label": "小红书",
        "width": 1080,
        "height": 1920,
        "vbr": "5M",
        "maxrate": "8M",
        "bufsize": "10M",
        "abr": "128k",
        "orientation": "portrait",
    },
    "bilibili": {
        "label": "B站",
        "width": 1920,
        "height": 1080,
        "vbr": "8M",
        "maxrate": "12M",
        "bufsize": "16M",
        "abr": "192k",
        "orientation": "landscape",
    },
    "youtube": {
        "label": "YouTube",
        "width": 1920,
        "height": 1080,
        "vbr": "10M",
        "maxrate": "16M",
        "bufsize": "20M",
        "abr": "192k",
        "orientation": "landscape",
    },
    "wechat": {
        "label": "微信聊天发送",
        "width": 1280,
        "height": 720,
        "vbr": "2M",
        "maxrate": "3M",
        "bufsize": "4M",
        "abr": "96k",
        "orientation": "keep",
    },
}

# 面向普通用户的体积档位：目标码率自动换算
SIZE_PRESETS = {
    "small": {"label": "小（发群聊、微信发送）", "height_cap": 720, "crf": 26},
    "medium": {"label": "中（日常分享、社交平台）", "height_cap": 1080, "crf": 23},
    "high": {"label": "高（存档、二次剪辑）", "height_cap": 1080, "crf": 20},
}

# 只有「音视频容器 → 音视频容器」之间比较体积才有意义。
# 抽字幕（.srt）、抽帧（.jpg）、动图（.gif）这类输出体积天然比源文件小几个数量级，
# 套用体积对比会得出「-100%」这类假结论，误导用户。
MEDIA_OUT_EXTS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v", ".ts",
    ".mpg", ".mpeg", ".wmv", ".m2ts", ".ogv",
    ".m4a", ".mp3", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma",
}


# ---------------------------------------------------------------- ffprobe


def run_stdout(cmd: list[str], timeout: int = TIMEOUT) -> str:
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


def ffprobe_json(path: str) -> dict | None:
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    raw = run_stdout(
        [
            probe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ]
    )
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def parse_fraction(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            return round(float(num) / den_f, 3) if den_f else None
        return round(float(value), 3)
    except (ValueError, ZeroDivisionError):
        return None


def to_int(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def human_duration(seconds: float | None) -> str:
    if not seconds:
        return "未知"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} 小时 {m} 分 {s} 秒"
    if m:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"


def human_size(num_bytes: int | None) -> str:
    if not num_bytes:
        return "未知"
    mb = num_bytes / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def get_rotation(stream: dict) -> int:
    """读取旋转元数据。手机竖拍视频常靠这个标记方向。"""
    tags = stream.get("tags") or {}
    for key in ("rotate", "rotation"):
        if key in tags:
            try:
                return int(float(str(tags[key]).strip()))
            except ValueError:
                pass
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return int(float(side["rotation"]))
            except (TypeError, ValueError):
                pass
    return 0


# ---------------------------------------------------------------- 分析


def analyze(path: str) -> dict:
    file_path = Path(path)
    result: dict = {
        "file": str(file_path),
        "exists": file_path.exists(),
        "name": file_path.name,
    }

    if not file_path.exists():
        result["error"] = "文件不存在"
        return result

    probe = shutil.which("ffprobe")
    if not probe:
        result["error"] = "未找到 ffprobe，请先安装 ffmpeg"
        return result

    data = ffprobe_json(str(file_path))
    if not data:
        result["error"] = "无法解析该文件，可能不是有效的视频或已损坏"
        return result

    fmt = data.get("format") or {}
    streams = data.get("streams") or []

    duration = None
    try:
        duration = round(float(fmt.get("duration")), 2)
    except (TypeError, ValueError):
        for s in streams:
            if s.get("duration"):
                try:
                    duration = round(float(s["duration"]), 2)
                    break
                except ValueError:
                    continue

    result["duration_sec"] = duration
    result["duration_human"] = human_duration(duration)
    result["size_bytes"] = to_int(fmt.get("size"))
    result["size_human"] = human_size(to_int(fmt.get("size")))
    result["format"] = fmt.get("format_name")
    result["overall_bitrate_kbps"] = (
        round(to_int(fmt.get("bit_rate"), 0) / 1000, 1) if fmt.get("bit_rate") else None
    )

    # 视频流
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if video_streams:
        v = video_streams[0]
        rotation = get_rotation(v)
        width = to_int(v.get("width"))
        height = to_int(v.get("height"))
        if rotation in (90, 270) and width and height:
            width, height = height, width
        result["video"] = {
            "codec": v.get("codec_name"),
            "profile": v.get("profile"),
            "width": width,
            "height": height,
            "fps": parse_fraction(v.get("avg_frame_rate") or v.get("r_frame_rate")),
            "pix_fmt": v.get("pix_fmt"),
            "bitrate_kbps": (
                round(to_int(v.get("bit_rate"), 0) / 1000, 1) if v.get("bit_rate") else None
            ),
            "rotation": rotation,
            "has_b_frames": to_int(v.get("has_b_frames")),
        }
        if width and height:
            ratio = width / height
            result["aspect_ratio"] = round(ratio, 3)
            if ratio < 0.95:
                result["orientation"] = "portrait"
                result["orientation_label"] = "竖屏"
            elif ratio > 1.05:
                result["orientation"] = "landscape"
                result["orientation_label"] = "横屏"
            else:
                result["orientation"] = "square"
                result["orientation_label"] = "方形"
    else:
        result["video"] = None
        result["note_no_video"] = "该文件不含画面轨道，无法作为视频处理"

    # 音频流
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    result["audio"] = [
        {
            "index": a.get("index"),
            "codec": a.get("codec_name"),
            "channels": to_int(a.get("channels")),
            "sample_rate": to_int(a.get("sample_rate")),
            "bitrate_kbps": (
                round(to_int(a.get("bit_rate"), 0) / 1000, 1) if a.get("bit_rate") else None
            ),
            "language": ((a.get("tags") or {}).get("language") or "").strip() or None,
        }
        for a in audio_streams
    ]

    # 字幕流
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    result["subtitles"] = [
        {
            "index": s.get("index"),
            "codec": s.get("codec_name"),
            "language": ((s.get("tags") or {}).get("language") or "").strip() or None,
            "title": ((s.get("tags") or {}).get("title") or "").strip() or None,
        }
        for s in sub_streams
    ]
    result["has_subtitle_track"] = bool(sub_streams)

    result["stream_count"] = len(streams)
    return result


# ---------------------------------------------------------------- 参数推导


def build_advice(info: dict, target: str | None) -> dict:
    advice: dict = {"options": [], "warnings": [], "suggested_commands": []}

    if info.get("error") or not info.get("video"):
        if info.get("error"):
            advice["warnings"].append(info["error"])
        elif info.get("note_no_video"):
            advice["warnings"].append(info["note_no_video"])
            advice["options"].append(
                {
                    "id": "audio_only",
                    "label": "这个文件只有声音，没有画面",
                    "hint": "可提取音频、调音量、降噪，或转成其它音频格式",
                }
            )
        return advice

    v = info["video"]
    fps = v.get("fps") or 30
    height = v.get("height") or 1080
    orientation = info.get("orientation", "landscape")
    bitrate = info.get("overall_bitrate_kbps") or 0

    # 1) 是否需要压体积
    if bitrate and bitrate > 4000:
        advice["options"].append(
            {
                "id": "compress",
                "label": f"压缩体积（当前 {bitrate:.0f} kbps，偏大）",
                "hint": "画质几乎看不出差别，体积可减少一半以上",
            }
        )
    else:
        advice["options"].append(
            {
                "id": "compress",
                "label": "压缩体积",
                "hint": "适合发送、上传，减少等待时间",
            }
        )

    # 2) 是否需要转竖屏
    if target and PLATFORM_SPECS.get(target, {}).get("orientation") == "portrait":
        need_portrait = orientation != "portrait"
    else:
        need_portrait = False
    if orientation == "landscape":
        advice["options"].append(
            {
                "id": "vertical",
                "label": "转成竖屏（横屏视频发抖音 / 视频号 / 小红书）",
                "hint": "上下补模糊背景，画面完整不变形",
                "needs_convert": True,
            }
        )
    if need_portrait:
        advice["warnings"].append("当前是横屏，而目标平台以竖屏为主，建议选择转竖屏")

    # 3) 编码兼容性
    if v.get("codec") not in ("h264",):
        advice["options"].append(
            {
                "id": "compat",
                "label": f"转成通用 H.264（当前 {v.get('codec')}，部分平台不认）",
                "hint": "提高各平台播放兼容性",
            }
        )

    # 4) 字幕轨
    if info.get("has_subtitle_track"):
        langs = [s.get("language") or "未知" for s in info["subtitles"]]
        advice["options"].append(
            {
                "id": "extract_subtitle",
                "label": f"提取自带字幕（检测到 {len(info['subtitles'])} 条字幕轨：{', '.join(langs)}）",
                "hint": "导出为 srt 文本文件",
            }
        )

    # 5) 无字幕轨时的语音转字幕提示
    if not info.get("has_subtitle_track") and info.get("audio"):
        advice["options"].append(
            {
                "id": "gen_subtitle",
                "label": "给视频生成字幕（语音自动识别）",
                "hint": "需要 whisper 引擎与本机模型，首次使用需下载",
            }
        )

    # 6) 目标平台建议
    if target and target in PLATFORM_SPECS:
        spec = PLATFORM_SPECS[target]
        advice["target_spec"] = spec
        if spec["orientation"] == "portrait" and orientation == "landscape":
            advice["warnings"].append(
                f"{spec['label']} 以竖屏为主，横屏视频建议先转竖屏再发布"
            )

    # 7) 体积与时长提示
    advice["summary"] = (
        f"{info.get('orientation_label', '未知')} "
        f"{v.get('width')}x{v.get('height')} · {fps:.2f}fps · "
        f"{info.get('duration_human')} · {info.get('size_human')}"
    )
    if info.get("duration_sec") and info["duration_sec"] > 600:
        advice["warnings"].append(
            f"时长 {info['duration_human']}，转码耗时较久，建议先确认处理方案再执行"
        )
    return advice


def target_bitrate_for_size(size_mb: float, duration_sec: float, audio_kbps: int = 128) -> int:
    """按「目标体积」反推视频码率（kbps），留 3% 容器开销。"""
    if duration_sec <= 0:
        return 2000
    total_kbits = size_mb * 8 * 1024 * 0.97
    v_kbps = total_kbits / duration_sec - audio_kbps
    return max(300, int(v_kbps))


SHELL_UNSAFE = set(" []()?*|&$#;<>'\"\t\n\\")


def render_cmd(args: list[str]) -> str:
    """把参数列表渲染成可直接粘贴进 bash / zsh 执行的命令串。

    必须显式加引号，否则两类参数会出错：
      - `0:a?` 在 zsh 下被当作 glob，报 "no matches found"
      - `scale=1080:1920:(ow-iw)/2` 的圆括号同理
    """
    parts = []
    for arg in args:
        if arg and any(ch in SHELL_UNSAFE for ch in arg):
            parts.append("'" + arg.replace("'", "'\\''") + "'")
        else:
            parts.append(arg)
    return " ".join(parts)


def build_commands(info: dict, target: str | None, outdir: str) -> list[dict]:
    """生成可直接执行的建议命令。

    每条命令同时保存两种表示：
      - args：参数列表，供 --run 直接执行（不经 shell，最可靠）
      - command：渲染后的命令串，供展示与手动粘贴

    两个硬约束：
      1. 输出名一律加后缀，绝不与源文件同名，避免覆盖素材
      2. 参数列表里不写转义符，转义统一交给 render_cmd 处理
    """
    cmds: list[dict] = []
    if info.get("error") or not info.get("video"):
        return cmds

    src = info["file"]
    stem = Path(src).stem
    out_dir = Path(outdir)
    v = info["video"]
    orientation = info.get("orientation", "landscape")
    spec = PLATFORM_SPECS.get(target) if target else None
    out_dir.mkdir(parents=True, exist_ok=True)

    def _out(suffix: str, ext: str = ".mp4") -> str:
        return str(out_dir / f"{stem}_{suffix}{ext}")

    def _add(cmd_id: str, label: str, args: list[str], output: str) -> None:
        cmds.append(
            {
                "id": cmd_id,
                "label": label,
                "output": output,
                "args": args,
                "command": render_cmd(args),
            }
        )

    # 1) 压缩体积。仅当高于 1080p 才降分辨率，避免小视频被放大。
    height = v.get("height") or 1080
    cap = SIZE_PRESETS["medium"]["height_cap"]
    compress_out = _out("compressed")
    args = ["ffmpeg", "-hide_banner", "-i", src]
    if height > cap:
        args += ["-vf", f"scale=-2:{cap}"]
    args += [
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        compress_out,
    ]
    _add("compress", "压缩体积", args, compress_out)

    # 2) 转竖屏：上下补模糊背景，画面完整、不裁切、不变形。
    if orientation == "landscape":
        if spec and spec["orientation"] == "portrait":
            w, h = spec["width"], spec["height"]
        else:
            w, h = 1080, 1920
        chain = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma=20[bgx];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgx];"
            f"[bgx][fgx]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
        )
        vertical_out = _out("vertical")
        args = [
            "ffmpeg", "-hide_banner",
            "-i", src,
            "-filter_complex", chain,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            vertical_out,
        ]
        _add("vertical", "转竖屏（补模糊背景）", args, vertical_out)

    # 3) 按目标平台规格输出
    if spec:
        pub_out = _out(f"for_{target}")
        args = [
            "ffmpeg", "-hide_banner",
            "-i", src,
            "-vf",
            f"scale={spec['width']}:{spec['height']}:force_original_aspect_ratio=decrease,"
            f"pad={spec['width']}:{spec['height']}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:v", "libx264",
            "-b:v", spec["vbr"],
            "-maxrate", spec["maxrate"],
            "-bufsize", spec["bufsize"],
            "-c:a", "aac",
            "-b:a", spec["abr"],
            "-movflags", "+faststart",
            pub_out,
        ]
        _add(
            f"publish_{target}",
            f"输出 {spec['label']} 规格（{spec['width']}x{spec['height']}）",
            args,
            pub_out,
        )

    # 4) 提取自带字幕轨
    if info.get("has_subtitle_track"):
        idx = info["subtitles"][0]["index"]
        sub_out = str(out_dir / f"{stem}.srt")
        args = ["ffmpeg", "-hide_banner", "-i", src, "-map", f"0:{idx}", sub_out]
        _add("extract_subtitle", "提取字幕为 srt", args, sub_out)

    return cmds


# ---------------------------------------------------------------- 输出


def render_human(info: dict, advice: dict) -> str:
    out = []
    out.append("=" * 62)
    out.append(f"文件：{info.get('name')}")
    out.append("=" * 62)
    if info.get("error"):
        out.append(f"读取失败：{info['error']}")
        out.append("=" * 62)
        return "\n".join(out)

    v = info.get("video")
    out.append(f"时长      {info.get('duration_human')}")
    out.append(f"体积      {info.get('size_human')}")
    if v:
        out.append(
            f"画面      {v.get('width')}x{v.get('height')} "
            f"{info.get('orientation_label')} · {v.get('fps')}fps · {v.get('codec')}"
        )
    else:
        out.append("画面      无（该文件不含画面轨道）")
    if info.get("audio"):
        a = info["audio"][0]
        out.append(
            f"声音      {a['codec']} · {a['channels']} 声道 · {a['sample_rate']}Hz"
        )
    else:
        out.append("声音      无")
    if info.get("subtitles"):
        out.append(f"字幕轨    {len(info['subtitles'])} 条")
    else:
        out.append("字幕轨    无")

    if advice.get("options"):
        out.append("")
        out.append("可选处理方式")
        for i, opt in enumerate(advice["options"], 1):
            out.append(f"  {i}. {opt['label']}")
            out.append(f"     {opt['hint']}")
    if advice.get("warnings"):
        out.append("")
        for w in advice["warnings"]:
            out.append(f"  提示  {w}")
    out.append("=" * 62)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="视频参数探测与处理方案推导")
    parser.add_argument("files", nargs="+", help="待探测的视频文件")
    parser.add_argument("--human", action="store_true", help="输出人类可读报告")
    parser.add_argument(
        "--target",
        choices=sorted(PLATFORM_SPECS.keys()),
        help="目标发布平台，用于推导分辨率与码率",
    )
    parser.add_argument(
        "--outdir", default=".", help="建议命令的输出目录（默认当前目录）"
    )
    parser.add_argument(
        "--size",
        type=float,
        help="目标体积（MB），用于反推码率，例如 --size 50",
    )
    parser.add_argument("--list", action="store_true", help="只列出可用命令 id")
    parser.add_argument(
        "--run",
        metavar="ID",
        help="直接执行指定 id 的命令，例如 --run compress（不经 shell，最稳）",
    )
    args = parser.parse_args()

    results = []
    for path in args.files:
        info = analyze(path)
        advice = build_advice(info, args.target)
        commands = build_commands(info, args.target, args.outdir)
        if args.size and info.get("duration_sec"):
            kbps = target_bitrate_for_size(args.size, info["duration_sec"])
            advice["target_size_plan"] = {
                "size_mb": args.size,
                "video_bitrate_kbps": kbps,
                "formula": f"{args.size}MB 目标体积 ÷ {info['duration_sec']:.0f} 秒 → "
                f"视频码率约 {kbps} kbps",
            }
        results.append({"info": info, "advice": advice, "commands": commands})

    if args.list:
        for item in results:
            for c in item["commands"]:
                print(f"{c['id']}\t{c['label']}")
        return 0

    if args.run:
        for item in results:
            for c in item["commands"]:
                if c["id"] == args.run:
                    print(f"执行：{c['command']}", file=sys.stderr)
                    try:
                        proc = subprocess.run(c["args"])
                    except Exception as exc:
                        print(f"执行失败：{exc}", file=sys.stderr)
                        return 1
                    if proc.returncode == 0:
                        print(f"完成，输出：{c['output']}", file=sys.stderr)
                        src_file = Path(item["info"]["file"])
                        out_file = Path(c["output"])
                        if (
                            out_file.exists()
                            and src_file.exists()
                            and out_file.suffix.lower() in MEDIA_OUT_EXTS
                        ):
                            src_size = src_file.stat().st_size
                            new_size = out_file.stat().st_size
                            if src_size:
                                delta = (new_size - src_size) / src_size * 100
                                print(
                                    f"体积：{src_size / 1048576:.1f}MB → "
                                    f"{new_size / 1048576:.1f}MB（{delta:+.0f}%）",
                                    file=sys.stderr,
                                )
                                if delta > -5:
                                    print(
                                        "提示：体积几乎没有减少。改用更强的压缩档位"
                                        "（把 crf 提到 28）重试。",
                                        file=sys.stderr,
                                    )
                    return proc.returncode
        available = [c["id"] for item in results for c in item["commands"]]
        print(
            f"未找到命令 id：{args.run}；可用：{', '.join(available) or '无'}",
            file=sys.stderr,
        )
        return 2

    if args.human:
        for item in results:
            print(render_human(item["info"], item["advice"]))
    else:
        payload = results[0] if len(results) == 1 else results
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
