# 视频处理码表

面向「说出想做什么」而不是「知道用什么参数」。每条都给出可直接执行的命令。

## 约定

- `{in}` = 输入视频路径，`{out}` = 输出视频路径。执行前替换成真实路径，路径含空格时要加引号。
- 所有命令**都不会覆盖源文件**，输出名必须与输入不同。
- 滤镜参数统一用单引号包裹，这样在 bash 和 zsh 下都能直接粘贴执行。
- `-map '0:a?'` 这类写法必须带引号：`?` 在 zsh 下会被当作通配符，报 `no matches found`。

## 当前环境能力提示

探测脚本已确认本机 ffmpeg 的编译限制，涉及以下两条时须先处理：

| 限制 | 影响 | 解决 |
|---|---|---|
| 未编译 libass | `subtitles` / `ass` 滤镜不存在，**无法把字幕烧进画面**；内挂软字幕不受影响 | `brew reinstall ffmpeg` |
| 未编译 freetype | `drawtext` 滤镜不存在，**无法在画面上叠加文字** | 同上，或改用图片水印 |
| 未编译 libsrt | 无法用 SRT 协议推流 | 需换带 libsrt 的构建 |

---

## A. 剪短与拼接

| 想做什么 | 命令 |
|---|---|
| 掐掉开头 10 秒 | `ffmpeg -ss 10 -i {in} -c copy {out}` |
| 只保留第 30 秒到 1 分 20 秒 | `ffmpeg -ss 30 -to 80 -i {in} -c copy {out}` |
| 精确到帧的剪切（前面那条更快但可能偏几帧） | `ffmpeg -i {in} -ss 30 -to 80 -c:v libx264 -crf 20 -c:a aac {out}` |
| 掐掉结尾 5 秒 | `ffmpeg -i {in} -t $(ffprobe -v error -show_entries format=duration -of csv=p=0 {in} | awk '{print $1-5}') -c copy {out}` |
| 丢掉中间一段（保留首尾拼接） | 见 `references/recipes.md` 多段裁剪配方 |
| 两个视频首尾相接 | `printf "file '%s'\n" {a} {b} > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy {out}` |
| 拼接参数不同的视频（先统一转码再接） | 见 `references/recipes.md` |

## B. 压缩与格式

| 想做什么 | 命令 |
|---|---|
| 压缩体积（推荐默认，画质损失小） | `ffmpeg -i {in} -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart {out}` |
| 压得更小（画质略降） | 把 `-crf 23` 改为 `-crf 28` |
| 画质优先（体积更大） | 把 `-crf 23` 改为 `-crf 18` |
| 压到约 50 MB | 见 `references/recipes.md` 目标体积配方 |
| 转成 H.265，体积约减半 | `ffmpeg -i {in} -c:v libx265 -crf 28 -tag:v hvc1 -c:a aac -b:a 128k {out}` |
| 只换封装不改画质（秒完成，无损） | `ffmpeg -i {in} -c copy {out}` |
| 降成 720p | `ffmpeg -i {in} -vf 'scale=-2:720' -c:v libx264 -crf 23 -c:a copy {out}` |
| 升成 1080p（不会真的变清晰） | `ffmpeg -i {in} -vf 'scale=-2:1080' -c:v libx264 -crf 20 -c:a copy {out}` |
| 手机拍的 MOV 转 MP4 | `ffmpeg -i {in} -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac {out}` |
| 输出能被所有平台播放的版本 | `ffmpeg -i {in} -c:v libx264 -profile:v high -level 4.1 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart {out}` |
| 用硬件加速快速转码（画质略逊） | `ffmpeg -i {in} -c:v h264_videotoolbox -b:v 6M -c:a aac {out}`（macOS；Windows/Linux 换 `h264_nvenc` 或 `h264_qsv`） |

## C. 尺寸与方向

| 想做什么 | 命令 |
|---|---|
| 横屏转竖屏，上下补模糊背景（不裁切、不变形） | `ffmpeg -i {in} -filter_complex '[0:v]split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bgx];[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgx];[bgx][fgx]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]' -map '[v]' -map '0:a?' -c:v libx264 -crf 20 -c:a aac {out}` |
| 横屏转竖屏，裁切填满（会切掉左右） | `ffmpeg -i {in} -vf 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920' -c:v libx264 -crf 20 -c:a copy {out}` |
| 转成方形 1:1 | `ffmpeg -i {in} -vf 'scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080' -c:v libx264 -crf 20 -c:a copy {out}` |
| 转成 4:3 或 16:9（补黑边） | `ffmpeg -i {in} -vf 'scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2:color=black' -c:v libx264 -crf 20 -c:a copy {out}` |
| 抖音 / 视频号规格（1080x1920） | `ffmpeg -i {in} -vf 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black' -c:v libx264 -b:v 6M -maxrate 8M -bufsize 12M -c:a aac -b:a 128k -movflags +faststart {out}` |
| 小红书规格（1080x1920） | 同抖音，`-b:v 5M -maxrate 8M` |
| B站 / YouTube 规格（1920x1080） | `ffmpeg -i {in} -vf 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black' -c:v libx264 -b:v 8M -maxrate 12M -bufsize 16M -c:a aac -b:a 192k -movflags +faststart {out}` |
| 微信聊天发送（1080p 以内小体积） | `ffmpeg -i {in} -vf 'scale=-2:720' -c:v libx264 -crf 28 -c:a aac -b:a 96k {out}` |

## D. 声音

| 想做什么 | 命令 |
|---|---|
| 声音太小，调大 2 倍 | `ffmpeg -i {in} -c:v copy -af 'volume=2.0' {out}` |
| 音量统一（不同片段声音忽大忽小） | `ffmpeg -i {in} -c:v copy -af 'loudnorm=I=-16:TP=-1.5:LRA=11' {out}` |
| 完全静音（保留画面） | `ffmpeg -i {in} -c:v copy -an {out}` |
| 去掉原声，换成别的音乐 | `ffmpeg -i {in} -i music.mp3 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest {out}` |
| 加背景音乐但要保留人声（音乐音量压低） | 见 `references/recipes.md` 混音配方 |
| 背景噪音大，降噪 | `ffmpeg -i {in} -c:v copy -af 'anlmdn=s=7:p=0.002' {out}` |
| 声音淡入 2 秒、淡出 3 秒 | `ffmpeg -i {in} -c:v copy -af 'afade=t=in:st=0:d=2,afade=t=out:st=8:d=3' {out}` |
| 快放 2 倍且声音不变调 | `ffmpeg -i {in} -filter_complex '[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]' -map '[v]' -map '[a]' {out}` |
| 慢放 0.5 倍且声音不变调 | `ffmpeg -i {in} -filter_complex '[0:v]setpts=2.0*PTS[v];[0:a]atempo=0.5[a]' -map '[v]' -map '[a]' {out}` |
| 只要声音，导出 MP3 | `ffmpeg -i {in} -vn -c:a libmp3lame -b:a 192k {out}` |
| 只要声音，导出无损 WAV | `ffmpeg -i {in} -vn -c:a pcm_s16le {out}` |

## E. 画面

| 想做什么 | 命令 |
|---|---|
| 画面方向不对，转正 90 度 | `ffmpeg -i {in} -vf 'transpose=1' -c:a copy {out}` |
| 左右镜像 | `ffmpeg -i {in} -vf 'hflip' -c:a copy {out}` |
| 自动裁掉黑边 | `ffmpeg -i {in} -vf 'cropdetect=24:2:0' -t 10 -f null -` 先看输出里的 `crop=` 值，再代入 `-vf 'crop=w:h:x:y'` |
| 手动裁掉右边 200 像素 | `ffmpeg -i {in} -vf 'crop=iw-200:ih:0:0' -c:a copy {out}` |
| 去水印 / 去台标（矩形区域） | `ffmpeg -i {in} -vf 'delogo=x=100:y=50:w=200:h=60:show=0' -c:a copy {out}` |
| 擦得更干净但更慢（用周围画面补） | 同上，去掉 `show=0` 先预览框选位置，再正式跑 |
| 调亮一点 | `ffmpeg -i {in} -vf 'eq=brightness=0.06:saturation=1.1' -c:a copy {out}` |
| 提高对比度 | `ffmpeg -i {in} -vf 'eq=contrast=1.15' -c:a copy {out}` |
| 转成黑白 | `ffmpeg -i {in} -vf 'hue=s=0' -c:a copy {out}` |
| 加图片水印到右上角 | `ffmpeg -i {in} -i logo.png -filter_complex '[1:v]scale=160:-1[wm];[0:v][wm]overlay=W-w-20:20' -c:a copy {out}` |
| 加图片水印到右下角（更常见） | `ffmpeg -i {in} -i logo.png -filter_complex '[1:v]scale=160:-1[wm];[0:v][wm]overlay=W-w-20:H-h-20' -c:a copy {out}` |
| **在画面上写字** | 当前 ffmpeg 缺 freetype，`drawtext` 不可用。先 `brew reinstall ffmpeg`，或把文字做成 PNG 用水印方式叠加 |
| 手持拍摄画面抖，防抖 | `ffmpeg -i {in} -vf 'deshake' -c:a copy {out}` |
| 画面偏糊，锐化一点 | `ffmpeg -i {in} -vf 'unsharp=5:5:1.0' -c:a copy {out}` |
| 柔化 / 磨皮感 | `ffmpeg -i {in} -vf 'gblur=sigma=1.5' -c:a copy {out}` |
| 淡入淡出（黑场过渡） | `ffmpeg -i {in} -vf 'fade=t=in:st=0:d=1,fade=t=out:st=9:d=1' -c:a copy {out}` |

## F. 字幕

| 想做什么 | 命令 |
|---|---|
| 抽出视频里的字幕文件 | `ffmpeg -i {in} -map '0:s:0' {out}` |
| 列出所有字幕轨 | `ffprobe -v error -select_streams s -show_entries stream=index,codec_name:stream_tags=language -of json {in}` |
| 内挂字幕（播放器可开关，不烧进画面） | `ffmpeg -i {in} -i sub.srt -map 0 -map 1 -c copy -c:s mov_text {out}` |
| 内挂字母前缀（MP4 用 mov_text，MKV 用 srt） | MKV 把 `mov_text` 换成 `srt` |
| 字幕转格式（srt 转 ass） | `ffmpeg -i sub.srt sub.ass` |
| **把字幕烧进画面** | 当前 ffmpeg 缺 libass，`subtitles` 滤镜不可用。先 `brew reinstall ffmpeg`，再执行 `ffmpeg -i {in} -vf "subtitles=sub.srt" -c:a copy {out}` |
| 语音自动生成字幕 | 见 `references/recipes.md` whisper 配方 |
| 字幕整体延后 1.5 秒 | 见 `references/recipes.md` 字幕偏移配方 |

## G. 图片与动图

| 想做什么 | 命令 |
|---|---|
| 截取第 5 秒的画面做封面 | `ffmpeg -ss 5 -i {in} -frames:v 1 -q:v 2 {out}.jpg` |
| 每秒抽一帧（做缩略图排查） | `ffmpeg -i {in} -vf 'fps=1' {out}_%04d.jpg` |
| 生成九宫格预览图 | `ffmpeg -i {in} -vf 'fps=1/5,scale=320:-1,tile=3x3' -frames:v 1 {out}.jpg`（九宫格需 9 帧，视频短于 45 秒会在格子里留空，此时把 `fps` 调大或改用 `tile=2x2`） |
| 视频转 GIF（ffmpeg 内置） | `ffmpeg -i {in} -vf 'fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse' {out}.gif` |
| 视频转 GIF（gifski，画质更好，需安装） | `ffmpeg -i {in} -vf 'fps=15,scale=640:-1' -f yuv4mpegpipe - | gifski --fps 15 -o {out}.gif -` |
| 图片序列合成视频 | `ffmpeg -framerate 30 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p {out}` |
| 静态图片做成 5 秒视频 | `ffmpeg -loop 1 -i photo.jpg -t 5 -vf 'scale=1080:-2' -c:v libx264 -pix_fmt yuv420p {out}` |

## H. 特殊效果

| 想做什么 | 命令 |
|---|---|
| 两段视频之间加交叉溶解转场 | `ffmpeg -i {a} -i {b} -filter_complex '[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];[v0][v1]xfade=transition=fade:duration=1:offset=7[v]' -map '[v]' {out}` |
| 左右并排对比 | `ffmpeg -i {a} -i {b} -filter_complex '[0:v]scale=-2:720[l];[1:v]scale=-2:720[r];[l][r]hstack' -c:a copy {out}` |
| 上下并排 | 同上，把 `hstack` 换成 `vstack` |
| 画中画（小窗放右下角） | `ffmpeg -i {main} -i {pip} -filter_complex '[1:v]scale=iw/3:-1[p];[0:v][p]overlay=W-w-20:H-h-20' -c:a copy {out}` |
| 画面更流畅（补帧到 60fps） | `ffmpeg -i {in} -vf 'minterpolate=fps=60' -c:a copy {out}` |
| 视频循环播放 3 次 | `ffmpeg -stream_loop 2 -i {in} -c copy {out}` |
| 加片头（把片头拼到前面） | 用 A 组的 concat 配方 |
| 画面缓慢推近（Ken Burns 效果） | `ffmpeg -i {in} -vf 'zoompan=z=min(zoom+0.0015,1.5):d=250:s=1080x1920' -c:a copy {out}` |

## I. 信息、批量与下载

| 想做什么 | 命令 |
|---|---|
| 查看视频的所有信息 | `ffprobe -v error -show_format -show_streams -of json {in}` |
| 只看分辨率和时长 | `ffprobe -v error -select_streams v:0 -show_entries stream=width,height -show_entries format=duration -of csv=p=0 {in}` |
| 批量压缩整个文件夹 | 见 `references/recipes.md` 批量配方 |
| 批量抽帧 | 见 `references/recipes.md` 批量配方 |
| 两个视频无损合并（参数必须一致） | `mkvmerge -o {out} {a} {b}`（需安装 mkvtoolnix） |
| 下载网络视频（含各平台） | `yt-dlp -f 'bv*+ba/b' -o '%(title)s.%(ext)s' {url}`（需安装 yt-dlp） |
| 下载并直接转成 MP4 | `yt-dlp -f 'bv*+ba/b' --recode-video mp4 {url}` |
| 自动剪掉所有静音停顿（粗剪利器） | `auto-editor {in} --output {out}`（需安装 auto-editor） |
| 只导出说话的部分 | `auto-editor {in} --edit 'audio:threshold=-30dB' --output {out}` |
| 查看媒体详细信息（比 ffprobe 易读） | `mediainfo {in}`（需安装 mediainfo） |
| 读写视频元数据 | `exiftool -Title='新标题' {in}`（需安装 exiftool） |

## J. 录制与直播

| 想做什么 | 命令 |
|---|---|
| 录屏（macOS，含系统声音需额外驱动） | `ffmpeg -f avfoundation -framerate 30 -i '1:0' -c:v libx264 -crf 20 -c:a aac {out}` |
| 录摄像头 | `ffmpeg -f avfoundation -framerate 30 -i '0:0' {out}` |
| 推流到直播平台 | `ffmpeg -re -i {in} -c:v libx264 -preset veryfast -b:v 4000k -maxrate 4000k -bufsize 8000k -c:a aac -b:a 128k -f flv rtmp://推流地址/推流码` |
| 把视频切成 HLS 分片（网站播放用） | `ffmpeg -i {in} -c:v libx264 -c:a aac -f hls -hls_time 6 -hls_playlist_type vod playlist.m3u8` |
| 从直播地址录制（存成文件） | `ffmpeg -i 'rtmp://地址' -c copy -f mp4 {out}` |

---

## 命令排查速查

| 报错 | 原因与对策 |
|---|---|
| `no matches found: 0:a?` | zsh 通配符展开。给参数加引号：`-map '0:a?'` |
| `Filter not found` / `No such filter: subtitles` | 该滤镜未编译进当前 ffmpeg。用 `detect_env.py` 查能力，或 `brew reinstall ffmpeg` |
| `Output file same as Input file` | 输出路径与输入相同。改输出名 |
| `Invalid argument` 出现在 `-vf` 后 | 滤镜表达式中的逗号被 shell 或 ffmpeg 误解析。整段用单引号包住 |
| 转出来没有声音 | 输入本身无音轨，或写了 `-an`。用 `ffprobe` 确认音轨是否存在 |
| 转出来画面偏色 / 发绿 | 编码器与像素格式不匹配。加 `-pix_fmt yuv420p` |
| 速度极慢 | 正在用 CPU 编码。加硬件编码参数，或降低 `-preset` 等级（如 `veryfast`） |
| 中文文件名乱码 | 终端编码问题。把文件重命名为英文再处理 |
