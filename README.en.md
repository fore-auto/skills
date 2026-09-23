# AUTO Skills

> Let AI do it for you — build a website, clean up your computer, control your hardware, find customers.

[![npm version](https://img.shields.io/npm/v/@fore-auto/skills.svg)](https://www.npmjs.com/package/@fore-auto/skills)
[![npm downloads](https://img.shields.io/npm/dm/@fore-auto/skills.svg)](https://www.npmjs.com/package/@fore-auto/skills)
[![license](https://img.shields.io/npm/l/@fore-auto/skills.svg)](./LICENSE)
[![node](https://img.shields.io/node/v/@fore-auto/skills.svg)](https://nodejs.org)

**AUTO brand Agent Skills collection.** Install once, then just describe what you need in your AI assistant's chat — no coding, no commands to memorise.

Website: <https://auto.fore.vip>

[简体中文](./README.md) | [English](./README.en.md)

---

## Quick start

```bash
# See what is available
npx @fore-auto/skills

# Install everything
npx @fore-auto/skills add --all

# Or install just one
npx @fore-auto/skills add auto-geo
```

Once installed, simply state what you need in your AI assistant — for example "clean up my computer", "build me a website", or "find me some customers".

---

## Skills

| Skill | Name | What it does |
|-------|------|--------------|
| `auto` | AUTO | The main entry. Give it a topic and get the steps most worth following. Some content requires unlocking. |
| `auto-site-builder` | Website Builder | Walks you from hosting and style choices through to deployment and search engine indexing. Already have a site? Start with a health check, then decide whether to optimise or rebuild. |
| `auto-geo` | GEO | Gets AI search engines to cite your content. Also finds B2B customers. |
| `auto-iot` | IoT Control | Controls smart home and maker hardware from your own computer: lights, plugs, air conditioning, curtains, Raspberry Pi, ESP32 and more. |
| `auto-pc-clear` | PC Optimiser | System health check, cache cleanup, disk space, startup items. Anything sensitive is confirmed with you first. Supports macOS / Windows / Linux. |
| `auto-prompt` | AUTO.Prompt | Makes AI think before it acts: strategy first, then execution, fewer wrong turns. |
| `auto-find-customers` | Find Customers | Tell it what you sell, it analyses who might buy and compiles a contactable customer list. Public information only. |

Get details for a specific skill:

```bash
npx @fore-auto/skills info auto-geo
```

---

## Install locations

| Option | Location | Scope |
|--------|----------|-------|
| Default | `~/.workbuddy/skills/` | Available in every project |
| With `--project` | `<current dir>/.workbuddy/skills/` | Current project only |

```bash
npx @fore-auto/skills add auto-iot --project
```

---

## Update and uninstall

```bash
# Update to the latest version (overwrites installed skills)
npx @fore-auto/skills add --all --force
```

To uninstall, just delete the skill folder — `~/.workbuddy/skills/` for user-level, or `.workbuddy/skills/` inside the project for project-level.

---

## Manual install

If `npx` is not available to you, you can install manually:

1. Download the skill folder you need from the [GitHub repository](https://github.com/fore-auto/skills);
2. Place it into `~/.workbuddy/skills/` (or `.workbuddy/skills/` inside your project);
3. Make sure the folder contains a `SKILL.md`.

---

## FAQ

**What environment do I need?**

An AI assistant client that supports Skills. Node.js 18 or later is required for the install command only.

**Will skills touch my files?**

Skills only act when you ask them to. Anything destructive or system-level is confirmed with you before it runs.

**Why does `auto` say content needs unlocking?**

The full execution steps in `auto` require unlocking. Visit <https://auto.fore.vip> for details.

---

## Feedback and support

- Issues: [GitHub Issues](https://github.com/fore-auto/skills/issues)
- Email: hi@fore.vip
- Website: <https://auto.fore.vip>

---

## License

[MIT](./LICENSE) © 2026 fore.vip
