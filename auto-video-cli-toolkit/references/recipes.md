# 多步配方

码表里用一句话说不清的操作，这里给出完整可执行的方案。所有脚本都使用 bash 语法；Windows 用户可把同样的命令逐条粘贴到 PowerShell 执行。

## 1. 压到指定体积（例如 50 MB）

单遍编码难以精确命中目标体积，用两遍编码。先按目标体积反算码率。

```bash
#!/usr/bin/env bash
set -euo pipefail
IN="input.mp4"
TARGET_MB=50
AUDIO_KBPS=128

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
# 目标千比特总数去掉 3% 容器开销，再减去音频码率，得到视频码率
V_KBPS=$(awk -v mb="$TARGET_MB" -v d="$DUR" -v a="$AUDIO_KBPS" \
  'BEGIN { printf "%d", (mb*8*1024*0.97)/d - a }')

echo "时长 ${DUR}s，目标 ${TARGET_MB}MB → 视频码率 ${V_KBPS}k"

ffmpeg -y -i "$IN" -c:v libx264 -b:v "${V_KBPS}k" -pass 1 -an -f null /dev/null
ffmpeg -y -i "$IN" -c:v libx264 -b:v "${V_KBPS}k" -pass 2 \
       -c:a aac -b:a "${AUDIO_KBPS}k" -movflags +faststart "output.mp4"

rm -f ffmpeg2pass-*.log*
```

也可直接让探测脚本算：

```bash
python3 scripts/probe_media.py "$IN" --size 50 --target douyin
```

## 2. 丢掉中间一段（保留首尾）

ffmpeg 没有「删除区间」的概念，要把保留的两段分别切出来再拼接。

```bash
#!/usr/bin/env bash
set -euo pipefail
IN="input.mp4"
CUT_START=10      # 要删掉区间的起点（秒）
CUT_END=25        # 要删掉区间的终点（秒）

# 切出前半段（帧精确，重新编码）
ffmpeg -y -i "$IN" -t "$CUT_START" -c:v libx264 -crf 20 -c:a aac part1.mp4
# 切出后半段
ffmpeg -y -ss "$CUT_END" -i "$IN" -c:v libx264 -crf 20 -c:a aac part2.mp4

# 拼接
printf "file '%s'\n" part1.mp4 part2.mp4 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy output.mp4
rm -f part1.mp4 part2.mp4 list.txt
```

## 3. 拼接参数不同的多个视频

concat 直接复制流要求所有片段的分辨率、编码、帧率一致，否则会花屏或时长错乱。先统一转码再拼。

```bash
#!/usr/bin/env bash
set -euo pipefail
TARGET_W=1920; TARGET_H=1080; TARGET_FPS=30
mkdir -p norm

i=0
for f in clip_*.mp4; do
  out=$(printf "norm/%03d.mp4" "$i")
  ffmpeg -y -i "$f" \
    -vf "scale=${TARGET_W}:${TARGET_H}:force_original_aspect_ratio=decrease,\
pad=${TARGET_W}:${TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=${TARGET_FPS}" \
    -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p \
    -c:a aac -ar 48000 -ac 2 "$out"
  i=$((i+1))
done

printf "file '%s'\n" norm/*.mp4 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy output.mp4
```

## 4. 批量压缩整个文件夹

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="./videos"
DST="./compressed"
mkdir -p "$DST"
LOG="./compress.log"
: > "$LOG"

shopt -s nullglob
for f in "$SRC"/*.{mp4,mov,mkv,avi,MP4,MOV}; do
  name=$(basename "$f")
  out="$DST/${name%.*}_compressed.mp4"
  [ -f "$out" ] && { echo "跳过（已存在）：$name"; continue; }
  echo "处理中：$name"
  if ffmpeg -y -hide_banner -loglevel error -i "$f" \
       -c:v libx264 -crf 23 -preset medium -pix_fmt yuv420p \
       -c:a aac -b:a 128k -movflags +faststart "$out"; then
    before=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f")
    after=$(stat -f%z "$out" 2>/dev/null || stat -c%s "$out")
    echo "$name  压缩前 $((before/1024/1024))MB → 压缩后 $((after/1024/1024))MB" | tee -a "$LOG"
  else
    echo "$name  失败" | tee -a "$LOG"
  fi
done
echo "完成，明细见 $LOG"
```

批量处理必须满足三条：跳过已存在的输出、单个失败不中断整批、结果写日志。直接覆盖源文件的脚本不要写。

## 5. 加背景音乐但保留人声

音乐压低到人声之下，避免盖住说话声。

```bash
ffmpeg -y -i video.mp4 -i music.mp3 \
  -filter_complex "[1:a]volume=0.25,aloop=loop=-1:size=2e9[bg];\
[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest output.mp4
```

`volume=0.25` 是音乐音量比例，按需要调；`duration=first` 保证跟视频等长。

## 6. 用 whisper 自动生成字幕

分两步：先抽音频，再识别。

```bash
#!/usr/bin/env bash
set -euo pipefail
IN="video.mp4"
MODEL="$HOME/.cache/whisper/ggml-medium.bin"

# 1) 抽出 16kHz 单声道 WAV（whisper 要求的输入格式）
ffmpeg -y -i "$IN" -vn -ar 16000 -ac 1 -c:a pcm_s16le audio.wav

# 2) 首次使用需下载模型（约 1.5 GB，中文建议 medium 起步）
mkdir -p "$(dirname "$MODEL")"
[ -f "$MODEL" ] || curl -L \
  "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin" \
  -o "$MODEL"

# 3) 识别并直接输出 srt
whisper-cli -m "$MODEL" -f audio.wav -l zh -osrt -of subtitle

rm -f audio.wav
```

产出 `subtitle.srt`。想烧进画面需要 ffmpeg 带 libass。

## 7. 字幕整体平移时间轴

字幕比画面快了 1.5 秒，就用 `-itsoffset` 或先改 srt 再内挂。整体平移最简单的做法是重新生成字幕文件：

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="subtitle.srt"
OFFSET="-1.5"     # 负数=字幕提前，正数=字幕延后（秒）

python3 - "$SRC" "$OFFSET" <<'PY'
import re, sys
from pathlib import Path

src, offset = Path(sys.argv[1]), float(sys.argv[2])

def shift(ts: str) -> str:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    total = int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000 + offset
    total = max(total, 0.0)
    hh = int(total // 3600); mm = int(total % 3600 // 60)
    ss = int(total % 60); mmm = int(round((total - int(total)) * 1000))
    if mmm == 1000:
        ss, mmm = ss + 1, 0
    return f"{hh:02d}:{mm:02d}:{ss:02d},{mmm:03d}"

out = re.sub(
    r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})",
    lambda m: f"{shift(m.group(1))} --> {shift(m.group(2))}",
    src.read_text(encoding="utf-8-sig"),
)
src.with_name(src.stem + "_shifted.srt").write_text(out, encoding="utf-8")
print(f"已输出 {src.stem}_shifted.srt")
PY
```

## 8. 批量输出平台规格

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="./videos"; DST="./for_platform"; mkdir -p "$DST"

for f in "$SRC"/*.mp4; do
  name=$(basename "${f%.*}")
  # 抖音：1080x1920 竖屏
  ffmpeg -y -hide_banner -loglevel error -i "$f" \
    -vf "scale=1080:1920:force_original_aspect_ratio=decrease,\
pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" \
    -c:v libx264 -b:v 6M -maxrate 8M -bufsize 12M \
    -c:a aac -b:a 128k -movflags +faststart "$DST/${name}_douyin.mp4"
  # B站：1920x1080 横屏
  ffmpeg -y -hide_banner -loglevel error -i "$f" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black" \
    -c:v libx264 -b:v 8M -maxrate 12M -bufsize 16M \
    -c:a aac -b:a 192k -movflags +faststart "$DST/${name}_bilibili.mp4"
done
```

## 9. 横屏视频批量转竖屏（补模糊背景）

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="./videos"; DST="./vertical"; mkdir -p "$DST"

for f in "$SRC"/*.mp4; do
  name=$(basename "${f%.*}")
  ffmpeg -y -hide_banner -loglevel error -i "$f" \
    -filter_complex "[0:v]split=2[bg][fg];\
[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bgx];\
[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgx];\
[bgx][fgx]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]" \
    -map "[v]" -map '0:a?' \
    -c:v libx264 -crf 20 -preset medium -c:a aac -b:a 128k \
    -movflags +faststart "$DST/${name}_vertical.mp4"
done
```

注意 `-map '0:a?'` 的引号：`?` 在 zsh 中是通配符，不加引号会报 `no matches found`。
