#!/usr/bin/env node
/**
 * 中英文 README 同步校验
 *
 * 单一事实源：本模块同时被三处调用 ——
 *   1. `npm run docs:check`（单独跑）
 *   2. `scripts/prepublish.mjs`（发布闸门）
 *   3. `scripts/hooks/pre-commit`（提交闸门）
 *
 * 判定口径：中英文 README 的**结构**必须一致（章节数 / 代码块 / 表格行 / 分隔线）。
 * 文案本身不做比对 —— 翻译不要求逐字对应，但骨架不能漂移。
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** 需要成对维护的中英文文档 */
export const PAIRS = [['README.md', 'README.en.md']];

function metrics(file) {
  const text = fs.readFileSync(file, 'utf8');
  return {
    h2: (text.match(/^## /gm) || []).length,
    fences: (text.match(/^```/gm) || []).length,
    rows: (text.match(/^\|/gm) || []).length,
    rules: (text.match(/^---$/gm) || []).length,
  };
}

/**
 * @returns {{ issues: string[], notes: string[] }}
 */
export function checkReadmeSync() {
  const issues = [];
  const notes = [];

  for (const [zhName, enName] of PAIRS) {
    const zhPath = path.join(ROOT, zhName);
    const enPath = path.join(ROOT, enName);

    if (!fs.existsSync(zhPath)) {
      issues.push(`缺少 ${zhName}`);
      continue;
    }
    if (!fs.existsSync(enPath)) {
      issues.push(`缺少 ${enName} —— 中英文需成对维护`);
      continue;
    }

    const zh = metrics(zhPath);
    const en = metrics(enPath);
    const dims = [
      ['二级标题', zh.h2, en.h2],
      ['代码块标记', zh.fences, en.fences],
      ['表格行', zh.rows, en.rows],
      ['分隔线', zh.rules, en.rules],
    ];
    const drifted = dims.filter(([, a, b]) => a !== b);

    if (drifted.length) {
      issues.push(
        `${zhName} ↔ ${enName} 结构不一致：` +
        drifted.map(([name, a, b]) => `${name} ${a}/${b}`).join('，') +
        ' —— 改动一处后请同步另一语言'
      );
    } else {
      notes.push(
        `${zhName} ↔ ${enName} 结构一致` +
        `（${zh.h2} 章节 / ${zh.rows} 表格行 / ${zh.fences} 代码块标记 / ${zh.rules} 分隔线）`
      );
    }
  }

  return { issues, notes };
}

// ---------- 作为命令直接运行 ----------
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { issues, notes } = checkReadmeSync();
  for (const n of notes) console.log(`  ✓ ${n}`);
  for (const i of issues) console.log(`  ✗ ${i}`);
  if (issues.length) {
    console.log('');
    console.log('  中英文 README 必须同步更新：改了一份就同步另一份，再提交。');
    console.log('  确需临时跳过：git commit --no-verify');
    console.log('');
    process.exit(1);
  }
  process.exit(0);
}
