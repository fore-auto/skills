---
name: auto-video-cli-toolkit
slug: video-cli-toolkit
displayName: 视频工具包
display_name: 视频工具包
display_name_en: Video Toolkit
description: 视频工具包（fore.vip）。面向不懂命令行的用户，把「视频太大发不出去 / 剪掉一段 / 拼成一个 / 转竖屏发抖音 / 加字幕去字幕 / 提取或替换音频 / 转格式 / 做封面动图 / 一整个文件夹都要处理」这类口语需求，变成一次不用理解任何技术细节的完整处理。首次使用先探测本机环境（ffmpeg / yt-dlp / whisper / auto-editor 等），按操作系统给出最佳安装位置与命令并引导安装，没有管理员权限时走用户级兜底；随后探测素材参数（分辨率、时长、方向、音轨、字幕轨），自动推导分辨率、码率、输出路径等全部参数，用户只选结果、不填参数；本机引擎能力缺陷（如未编译字幕烧录能力）提前告知，不等失败才说。当用户说「视频压缩 / 视频太大了 / 微信发不了 / 剪视频 / 视频拼接 / 转竖屏 / 发抖音视频号小红书 / 提取字幕 / 去字幕 / 语音转文字 / 提取音频 / 换背景音乐 / 视频转格式 / 抽帧做封面 / 转 GIF / 去水印台标 / 批量处理视频 / 视频处理命令报错」时使用。也用于询问本机具备哪些视频处理能力、该装哪些视频工具。
description_zh: 面向不懂命令行的用户的视频处理助手。先探测本机环境并按操作系统引导安装所需工具（含无管理员权限的用户级兜底），再把口语化需求映射为可直接执行的命令，自动补全分辨率、码率、输出路径等全部参数；素材探测覆盖方向、时长、音轨与字幕轨。覆盖压缩体积、裁剪拼接、竖屏适配、平台发布规格、音量与降噪、字幕提取与生成、抽帧封面、GIF、区域去水印、批量处理。全程只读原文件、绝不覆盖、绝不删除。
description_en: "A video toolkit for people who would rather not touch the command line. It turns plain-language requests — this video is too big to send, cut out a clip, join these together, make it vertical for short-video platforms, add or remove subtitles, extract or replace the audio, convert the format, grab a cover frame, process a whole folder — into complete processing without the user learning a single flag. On first use it probes the machine (ffmpeg / yt-dlp / whisper / auto-editor and friends), then guides installation at the best location for the operating system, with a no-admin user-level fallback. It then probes the source file (resolution, duration, orientation, audio and subtitle tracks) and fills in every parameter — resolution, bitrate, output path — so the user picks an outcome instead of typing flags. Known engine limitations (such as a build without subtitle burn-in) are disclosed up front rather than after a failure. Use it for video compression, trimming, concatenation, vertical reframing, platform publish specs, audio cleanup, subtitle extraction or generation, cover frames, GIFs, logo removal and batch processing; also for asking what video tooling this machine has or what should be installed."
category: media
version: 1.0.0
author: fore.vip
owner: team
agent_created: true
triggers:
  - "视频压缩"
  - "视频太大了"
  - "微信发不了"
  - "剪视频"
  - "裁剪视频"
  - "视频拼接"
  - "合并视频"
  - "转竖屏"
  - "发抖音"
  - "发视频号"
  - "发小红书"
  - "提取字幕"
  - "去字幕"
  - "语音转文字"
  - "生成字幕"
  - "提取音频"
  - "换背景音乐"
  - "视频转格式"
  - "抽帧"
  - "做封面"
  - "转 GIF"
  - "去水印"
  - "批量处理视频"
  - "视频处理命令报错"
negative_triggers:
  - "图片批处理（应走图像处理能力）"
  - "纯音频文件的音乐制作与编曲"
  - "需要多轨时间线工程回改的专业剪辑"
---

# 视频工具包

把「我想把这个视频弄小一点」这类自然语言需求，转成不需要用户理解任何技术细节的完整执行。

## 核心原则

1. **用户不需要知道任何命令、参数或术语。** 所有技术选择由执行者决定并给出默认值。
2. **绝不覆盖源文件。** 输出名一律加后缀，且执行前确认输出路径与输入不同。
3. **绝不删除用户文件。** 本技能全程只做读取与新建。中间产物清理前必须先问。
4. **动手前先探测。** 不知道环境就下命令，是本技能最常见的失败原因。
5. **报错要翻译成人话。** 不要把引擎原始报错直接抛给用户。

## 目录约定

以下路径均相对于本技能目录：

- `scripts/detect_env.py` —— 环境探测，输出机器可读 JSON
- `scripts/probe_media.py` —— 素材探测与参数推导，可生成并直接执行命令
- `references/cheatsheet.md` —— 操作码表，按用户意图分类
- `references/install-matrix.md` —— 分系统安装位置与步骤
- `references/recipes.md` —— 多步配方（批量、目标体积、混音、字幕等）

脚本用 `python3` 执行；Windows 上用 `python`。若目标机器没有 Python，跳过脚本，直接依据 `references/cheatsheet.md` 的纯命令执行，环境判断改为逐条运行 `ffmpeg -version` 之类的探测命令。

---

## 执行流程

### 第 0 步 · 环境探测（每次会话首次触发时执行一次）

```bash
python3 scripts/detect_env.py
```

读取 JSON，重点看四个字段：

| 字段 | 含义 | 如何应对 |
|---|---|---|
| `ffmpeg.installed` | 是否装了引擎 | 为 `false` 时**什么都做不了**，必须先走第 1 步 |
| `gaps.rec` | 缺失的推荐工具 | 影响能不能做「自动剪静音」「下载视频」等操作 |
| `ffmpeg.limitations` | 引擎的能力缺陷 | 记下来，用户提到相关操作时**提前说明**，不要等失败 |
| `install_plan` | 待装工具与命令 | 第 1 步直接照用 |

不要把 JSON 原样丢给用户。翻译成一句结论即可，例如：

> 你的电脑已经装好视频处理引擎，可以开始。另外有 4 个增强工具没装，装上之后能自动剪掉静音停顿、下载网络视频。

### 第 1 步 · 补齐工具（仅在有缺口且用户同意时）

用选择的形式征求意见，不要擅自安装。参考话术：

- 选项 A：**只装必需的** —— 现在就够用，不影响手上这件事
- 选项 B：**推荐工具一并装好** —— 多出「自动剪静音」和「下载视频」的能力，占用约 200 MB
- 选项 C：**先不装** —— 直接开始处理

执行安装时的硬性要求：

1. 逐条执行 `install_plan` 里 `command` 字段的命令。
2. **`needs_admin` 为 `true` 的命令会索要管理员密码，执行前必须明确告知用户**，例如「接下来这条命令会要求你输入电脑密码，这是安装系统组件的正常步骤」。
3. 安装过程输出不要全量贴给用户，只报「正在装什么」「成功还是失败」。
4. 装完重跑一次 `detect_env.py --human` 验证，把工具状态变化告知用户。
5. 包名或通道失效时查 `references/install-matrix.md`，那里列了各系统各包管理器的完整对照，以及没有管理员权限时的兜底方案。

### 第 2 步 · 了解素材

拿到文件路径后先探测，不要凭文件名猜：

```bash
python3 scripts/probe_media.py "<文件路径>" --target <平台标识>
```

平台标识可选：`douyin` `shipinhao` `xiaohongshu` `bilibili` `youtube` `wechat`。不确定就不传。

把探测结果翻译成人话汇报，例如：

> 这个视频 2 分 03 秒，1080×1920 竖屏，456 MB，带一条字幕轨。
> 体积偏大，主要是码率过高 —— 压缩后画质几乎看不出差别，体积大概能减到三分之一。

**汇报时不要出现的词**：CRF、码率、bitrate、pix_fmt、yuv420p、filter_complex、GOP。

若 `advice.warnings` 非空，用一句话前置提醒，例如「你这条是横屏，但抖音主要看竖屏，建议先转成竖屏」。

### 第 3 步 · 给选项

把 `advice.options` 与通用菜单合并，用选择的形式呈现，**一次最多给 4 项**。选项文字描述结果，不描述手段。

通用菜单（`advice.options` 覆盖不到时补充）：

| 选项文字 | 对应用户意图 |
|---|---|
| 压缩体积，方便发送或上传 | 压缩 |
| 掐掉开头或结尾的一段 | 裁切 |
| 把几段视频拼成一个 | 拼接 |
| 转成竖屏，适合发短视频 | 竖屏适配 |
| 转成某个平台的发布规格 | 平台规格 |
| 换个方向或裁掉一部分画面 | 旋转裁切 |
| 处理声音：调音量、换音乐、降噪 | 音频 |
| 加字幕 / 提取字幕 / 生成字幕 | 字幕 |
| 做封面图、抽帧、转成动图 | 图片 |
| 擦掉画面里的水印或台标 | 去水印 |
| 一次性处理整个文件夹 | 批量 |

用户可以一次选多项，也可以自由描述。**不要要求用户提供任何技术参数**：需要哪一段、发哪个平台这类信息可以一句话追问，分辨率、码率、封装格式一律自己定。

### 第 4 步 · 执行

两条路径，优先第一条：

**路径 A —— 探测脚本已生成对应命令**

```bash
python3 scripts/probe_media.py "<文件>" --target <平台> --outdir "<输出目录>" --list
python3 scripts/probe_media.py "<文件>" --target <平台> --outdir "<输出目录>" --run <命令id>
```

`--run` 不经过 shell，能规避引号与通配符问题，是本技能的首选执行方式。

**路径 B —— 从码表取命令**

到 `references/cheatsheet.md` 按用户意图找到条目，替换 `{in}` `{out}` 后执行。若单个操作不够用（批量、目标体积、混音、字幕生成），改用 `references/recipes.md`。

执行时的强制约束：

1. **输出目录默认选在工作区内的 `video_output/`**，不要往桌面、下载等个人目录写文件。
2. 替换占位符后，先确认输出名与输入名不同。
3. 耗时预判：转码大体按「素材时长 × 0.5～3 倍」估算。超过 3 分钟的任务，先说一句预计耗时再执行。
4. 含 `?` 的参数（例如 `0:a?`）必须加引号，否则在 zsh 下会报 `no matches found`。
5. 一次只跑一条命令；批量任务改用 `references/recipes.md` 的脚本，脚本必须带「跳过已存在输出」和「单条失败不中断」。

### 第 5 步 · 验证与汇报

1. 确认输出文件存在且体积不为 0。
2. 用 `ffprobe` 抽查输出，确认时长、分辨率符合预期。
3. 汇报三件事即可：
   - 做了什么
   - 文件在哪（给完整路径）
   - 体积变化，例如「456 MB → 148 MB，减少 68%」
4. 主动问一句是否还要做别的处理；若用户先前提过但未完成的项还在，提醒一下。

---

## 需求到操作的映射

用户的原话通常不是术语。按下面的对应关系识别意图，再回到第 2～4 步。

| 用户会说 | 实际要做的 |
|---|---|
| 太大了 / 发不出去 / 微信发不了 | 压缩体积，必要时降到 720p |
| 太长了，只想要其中一段 | 裁切 |
| 掐掉开头 / 结尾 | 裁切 |
| 把这几段接起来 | 拼接；参数不一致时先统一转码 |
| 发抖音 / 视频号 / 小红书 | 竖屏适配 + 平台规格 |
| 发 B 站 / 上传 YouTube | 横屏 1080p 规格 |
| 画面歪了 / 倒了 | 旋转 |
| 有黑边 / 要裁掉一块 | 裁切 |
| 有台标 / 有水印 / 有 logo | 区域擦除 `delogo`，会有痕迹，需如实说明 |
| 声音太小 / 忽大忽小 | 音量调整 / 响度标准化 |
| 背景太吵 | 降噪 |
| 换个背景音乐 | 音轨替换 / 混音 |
| 加字幕 / 把字幕压上去 | 注意引擎若缺 libass 需先补装，见第 0 步 |
| 把字幕抽出来 | 抽取字幕轨 |
| 视频讲了什么 / 生成字幕 | whisper 语音识别，见 `references/recipes.md` |
| 要个封面 / 截一张图 | 抽帧 |
| 做成动图 / 表情包 | GIF |
| 剪掉说错的地方 / 去掉停顿 | `auto-editor`，需第 1 步装上 |
| 把网上的视频存下来 | `yt-dlp`，需第 1 步装上 |
| 一整个文件夹都要处理 | 批量配方 |

## 交互话术规范

技术事实转成人话，一律用右列表达：

| 技术表述 | 对用户说 |
|---|---|
| CRF 23 | 画质几乎看不出差别 |
| 1080×1920 | 竖屏，手机全屏 |
| 1920×1080 | 横屏，常见的高清 |
| 码率 6 Mbps | 每分钟大约 45 MB |
| 转码 | 重新处理一遍，需要一点时间 |
| 硬件加速 | 会快一些，画质略逊 |
| 无音轨 | 这个视频本身没有声音 |
| libass 未编译 | 当前引擎不支持把字幕压进画面，需要补装 |
| 引擎未安装 | 需要先装视频处理引擎，我来引导你完成 |

## 边界与禁止事项

- 不执行任何删除操作。中间文件（两遍编码的 log、临时 wav）清理前必须征得同意。
- 不修改、不移动用户的原文件。
- 不往桌面、下载、文稿等个人目录写输出，除非用户明确指定路径。
- 不承诺「提高清晰度」：低分辨率放大不会真的变清楚，遇到这类需求要如实说明。
- 不承诺 AI 级画面修复：本工具链不具备生成式修复能力，去水印只能做区域填充，会有痕迹。
- 涉及长时间高负载任务（补帧、逐帧处理）时先说明耗时，再询问是否继续。
- 用户明确表示不需要技术细节时，不要再解释原理，直接给结果。
