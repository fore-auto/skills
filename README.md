# AUTO Skills

> 让 AI 帮你自动建站、优化电脑、控制硬件、挖掘客户。

[![npm version](https://img.shields.io/npm/v/@fore-auto/skills.svg)](https://www.npmjs.com/package/@fore-auto/skills)
[![npm downloads](https://img.shields.io/npm/dm/@fore-auto/skills.svg)](https://www.npmjs.com/package/@fore-auto/skills)
[![license](https://img.shields.io/npm/l/@fore-auto/skills.svg)](./LICENSE)
[![node](https://img.shields.io/node/v/@fore-auto/skills.svg)](https://nodejs.org)

**AUTO 品牌 Agent Skills 合集**。装一次，在 AI 助手对话里说一句话就能用 —— 不用写代码，不用记命令。

官网：<https://auto.fore.vip>

---

## 快速开始

```bash
# 看看有哪些技能
npx @fore-auto/skills

# 一次装齐
npx @fore-auto/skills add --all

# 只装需要的
npx @fore-auto/skills add auto-geo
```

装好后在 AI 助手里直接说需求即可，比如「帮我优化下电脑」「给我搭个官网」「看看还缺哪些客户」。

---

## 技能清单

| 技能 | 名称 | 能做什么 |
|------|------|----------|
| `auto` | AUTO | 总入口。说一个主题，拿到这个主题最值得照做的执行步骤。部分内容需解锁后查看。 |
| `auto-site-builder` | 官网自动建站 | 从选托管、定风格到部署上线、被搜索引擎收录，一步步把官网搭起来。已有站点可以先做体检再决定优化还是重建。 |
| `auto-geo` | GEO | 让 AI 搜索在回答里引用你的内容。也给 B 端生意找客户。 |
| `auto-iot` | 智控 | 在电脑上统一控制智能家居和创客硬件：灯、插座、空调、窗帘、树莓派、ESP32 等。 |
| `auto-pc-clear` | 电脑优化 | 电脑体检、清缓存、腾硬盘、优化开机启动项。敏感操作会先问你。支持 macOS / Windows / Linux。 |
| `auto-prompt` | AUTO.Prompt | 让 AI 先想清楚再动手：先给策略，再执行，少走弯路。 |
| `auto-find-customers` | 找客户 | 说清你卖什么，分析谁可能买，整理出可联系的客户清单。只使用公开信息。 |

查看某个技能的详细信息：

```bash
npx @fore-auto/skills info auto-geo
```

---

## 安装位置

| 选项 | 安装位置 | 适用范围 |
|------|----------|----------|
| 默认 | `~/.workbuddy/skills/` | 所有项目都能用 |
| 加 `--project` | `<当前目录>/.workbuddy/skills/` | 只在当前项目生效 |

```bash
npx @fore-auto/skills add auto-iot --project
```

---

## 更新与卸载

```bash
# 更新到最新版（覆盖已安装的技能）
npx @fore-auto/skills add --all --force
```

卸载：删除对应技能目录即可（用户级在 `~/.workbuddy/skills/`，项目级在当前项目的 `.workbuddy/skills/`）。

---

## 手动安装

不方便使用 `npx` 时，也可以手动安装：

1. 从 [GitHub 仓库](https://github.com/fore-auto/skills) 下载需要的技能目录；
2. 放进 `~/.workbuddy/skills/`（或项目的 `.workbuddy/skills/`）；
3. 确认目录里有 `SKILL.md`。

---

## 常见问题

**需要什么环境？**

需要支持技能（Skill）的 AI 助手客户端。安装过程需要 Node.js 18 或更高版本，仅在使用 `npx` 时用到。

**技能会动我的文件吗？**

技能只在你主动要求时执行操作。涉及删除、修改系统设置等敏感动作，都会先向你确认。

**`auto` 提示需要解锁是什么？**

`auto` 的完整执行步骤需要解锁后查看，请到官网 <https://auto.fore.vip> 了解。

---

## 反馈与支持

- 问题反馈：[GitHub Issues](https://github.com/fore-auto/skills/issues)
- 邮箱：hi@fore.vip
- 官网：<https://auto.fore.vip>

---

## 许可

[MIT](./LICENSE) © 2026 fore.vip
