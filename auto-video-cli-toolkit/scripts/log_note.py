#!/usr/bin/env python3
"""auto-video-cli-toolkit · 经验回写器（技能自增长）

把在真实素材、真实机器上踩到并修好的问题，按统一格式追加进
`references/field-notes.md`，并把 `SKILL.md` 的版本号 PATCH +1。

设计约束：
  - **只追加**，不改写历史条目；靠编号与查重保证不重复。
  - 同一症状重复提交会被拒绝（返回码 3），避免同一个坑记十遍。
  - 只动本技能目录内的两个文件，不碰用户素材，不联网。

用法:
  python3 scripts/log_note.py --list
  python3 scripts/log_note.py \\
      --symptom "一句话症状" --cause "根因" --fix "修正做法" \\
      --verify "怎么确认修好了" [--scope "影响哪些操作"] [--env "环境"]
  加 --dry-run 只看将要写入的内容，不落盘。

退出码:
  0  写入成功（或 --list 正常结束）
  2  参数不完整 / 路径异常
  3  该症状已存在，未写入
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "references" / "field-notes.md"
SKILL_MD = ROOT / "SKILL.md"

ENTRY_RE = re.compile(r"^## (FN-\d+) · (.+)$", re.M)

PUNCT = set(
    "，。、；：！？（）「」『』《》〔〕【】"
    ",.;:!?()[]{}<>\"'`~@#$%^&*_-+=|\\/ \t\r\n\u3000"
)

# 字符相似度阈值：达到即视为「疑似重复」，需 --force 才写入
SIMILAR_THRESHOLD = 0.80

HEADER = """# 实战经验库（field-notes）

> 本文件是技能的**自增长记录**：每一次在真实素材、真实机器上踩到并修好的问题，都在这里留一条。
> 只追加，不改历史条目。发现旧条目过时，新增一条说明并互相引用。

## 记录规则

**写什么**

- 码表命令在真实素材上失败、并被修正过的
- 引擎/工具行为与预期不符（编译开关缺失、参数语义变化、平台规格变更）
- 用户实际报错里出现的、文档没覆盖的症状
- 找到更短路径或更稳定的替代做法

**不写什么**

- 一次性环境故障（磁盘满、网络抖动、机器当时卡死）
- 未经复现的猜测；只出现过一次的偶发
- 与技能职责无关的失败

**判断标准**：这个坑明天换一台机器、换一个人来做，还会不会踩？会 → 写。

**写的方式**：用 `scripts/log_note.py` 回写，不要手改本文件。脚本负责编号、查重、递进版本号。

```bash
python3 scripts/log_note.py \\
  --symptom "一句话症状（用户视角）" \\
  --cause "根因（技术视角）" \\
  --fix "修正做法（可复制的命令或规则）" \\
  --verify "怎么确认修好了" \\
  --scope "影响哪些操作"
```

**查阅时机**：第 0 步环境探测之后、以及任何命令报错时，先在本文件里搜症状关键词，再决定要不要动手排查。

---
"""


def normalize(text: str) -> str:
    """去掉空白与标点后小写化，用于查重比对。"""
    return "".join(ch for ch in text.casefold() if ch not in PUNCT)


def load_entries(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip()) for m in ENTRY_RE.finditer(text)]


def next_number(entries: list[tuple[str, str]]) -> int:
    nums = [int(e[0].split("-")[1]) for e in entries] or [0]
    return max(nums) + 1


def find_duplicate(symptom: str, entries: list[tuple[str, str]]):
    """返回 (命中编号, 是否完全重复, 相似度)。没有命中时编号为 None。

    判定分两级：
      1. 归一化后完全一致 → 完全重复，一律拒绝（同一件事记十遍没有价值）；
      2. 字符相似度 ≥ SIMILAR_THRESHOLD → 疑似重复，要求 --force 才写入。

    字符级比对能抓住加字、减字、换标点的改写；纯粹的换句表达（「少了一半
    体积」vs「体积缩减 50%」）抓不到，那种情况执行者看到提示词后自行判断。
    """
    target = normalize(symptom)
    if not target:
        return None, False, 0.0

    for num, title in entries:
        if normalize(title) == target:
            return num, True, 1.0

    best_num, best_ratio = None, 0.0
    for num, title in entries:
        ratio = difflib.SequenceMatcher(None, target, normalize(title)).ratio()
        if ratio > best_ratio:
            best_num, best_ratio = num, ratio

    if best_num and best_ratio >= SIMILAR_THRESHOLD:
        return best_num, False, best_ratio
    return None, False, best_ratio


def build_entry(number: int, args) -> str:
    scope = args.scope or "未标注"
    env = args.env or "未标注"
    return (
        f"## FN-{number:03d} · {args.symptom.strip()}\n\n"
        f"- **记录日期**：{date.today().isoformat()}\n"
        f"- **环境**：{env}\n"
        f"- **症状**：{args.symptom.strip()}\n"
        f"- **根因**：{args.cause.strip()}\n"
        f"- **修正做法**：{args.fix.strip()}\n"
        f"- **验证**：{args.verify.strip()}\n"
        f"- **影响面**：{scope}\n"
    )


def bump_patch_version() -> tuple[str, str] | None:
    """把 SKILL.md frontmatter 的 version 第三位 +1。"""
    if not SKILL_MD.exists():
        return None
    text = SKILL_MD.read_text(encoding="utf-8")
    head = re.match(r"^---\n(.*?\n)---\n", text, re.S)
    if not head:
        return None
    fm = head.group(1)
    vm = re.search(r"^version:\s*(\d+)\.(\d+)\.(\d+)\s*$", fm, re.M)
    if not vm:
        return None

    old = vm.group(0).split(":", 1)[1].strip()
    new = f"{vm.group(1)}.{vm.group(2)}.{int(vm.group(3)) + 1}"
    new_fm = fm[: vm.start()] + f"version: {new}" + fm[vm.end():]
    SKILL_MD.write_text(
        text[: head.start(1)] + new_fm + text[head.end(1):], encoding="utf-8"
    )
    return old, new


def registry_reminder(new_version: str | None) -> list[str]:
    """技能被收进家族仓库时，package.json 里也登记了版本号，提醒同步。"""
    notes: list[str] = []
    pkg = ROOT.parent / "package.json"
    if not pkg.exists():
        return notes
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return notes
    for item in data.get("skills", []):
        if item.get("name") != ROOT.name:
            continue
        current = item.get("version")
        if new_version and current == new_version:
            return notes  # 已经一致，不必提醒
        notes.append(
            f"家族仓库登记版本需同步：{pkg} 里 {ROOT.name} 当前为 "
            f"{current}，应改为 {new_version}"
        )
        return notes
    return notes


def cmd_list() -> int:
    if not NOTES.exists():
        print("经验库尚不存在，尚无任何记录。", file=sys.stdout)
        return 0
    entries = load_entries(NOTES.read_text(encoding="utf-8"))
    if not entries:
        print("经验库为空，尚无任何记录。", file=sys.stdout)
        return 0
    print(f"经验库共 {len(entries)} 条：")
    for num, title in entries:
        print(f"  {num}  {title}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把已修好的实际问题回写进技能经验库，并递进 PATCH 版本号"
    )
    parser.add_argument("--list", action="store_true", help="列出已有条目")
    parser.add_argument("--symptom", help="症状（用户视角，一句话）")
    parser.add_argument("--cause", help="根因（技术视角）")
    parser.add_argument("--fix", help="修正做法（可复制的命令或规则）")
    parser.add_argument("--verify", help="怎么确认修好了")
    parser.add_argument("--scope", help="影响哪些操作")
    parser.add_argument("--env", help="环境（系统 / 版本 / 素材规格）")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不落盘")
    parser.add_argument("--force", action="store_true", help="疑似重复时仍写入")
    args = parser.parse_args()

    if args.list:
        return cmd_list()

    missing = [
        name
        for name in ("symptom", "cause", "fix", "verify")
        if not (getattr(args, name) or "").strip()
    ]
    if missing:
        print(
            "参数不完整，缺少：" + "、".join("--" + m for m in missing) + "\n"
            "四个必填项：--symptom --cause --fix --verify",
            file=sys.stderr,
        )
        return 2

    if not NOTES.parent.exists():
        print(f"路径异常：找不到 {NOTES.parent}", file=sys.stderr)
        return 2

    NOTES.parent.mkdir(parents=True, exist_ok=True)
    if NOTES.exists():
        text = NOTES.read_text(encoding="utf-8")
        if not text.strip():
            text = HEADER + "\n"
    else:
        text = HEADER + "\n"

    entries = load_entries(text)
    hit, exact, ratio = find_duplicate(args.symptom, entries)

    if hit and exact:
        print(
            f"已存在完全相同的症状：{hit}。本次未写入。\n"
            "若只是同一问题再次复现，请在该条目下补一行复现日期，不必新增条目。",
            file=sys.stderr,
        )
        return 3
    if hit and not exact:
        if not args.force:
            print(
                f"疑似与已有条目 {hit} 重复（字符相似度 {ratio:.0%}），本次未写入。\n"
                "确认是不同问题：加 --force 再跑一次；"
                f"确认是同一个坑：在 {hit} 下补一行即可。",
                file=sys.stderr,
            )
            return 3
        print(
            f"注意：与已有条目 {hit} 疑似重复（字符相似度 {ratio:.0%}），"
            "按 --force 强制写入。",
            file=sys.stderr,
        )

    number = next_number(entries)
    entry = build_entry(number, args)

    if args.dry_run:
        print("—— 预览（未落盘）——")
        print(entry)
        return 0

    if not text.endswith("\n"):
        text += "\n"
    NOTES.write_text(text + "\n" + entry, encoding="utf-8")
    print(f"已写入 {NOTES.name}：FN-{number:03d} · {args.symptom.strip()}")

    bumped = bump_patch_version()
    if bumped:
        print(f"版本号已递进：{bumped[0]} → {bumped[1]}")
    else:
        print("提示：未能识别 SKILL.md 的 version 字段，版本号未改动，请人工核对。")

    for line in registry_reminder(bumped[1] if bumped else None):
        print("提示：" + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
