#!/usr/bin/env node
/**
 * 发布前校验 —— npm run check / prepublishOnly 自动调用
 *
 * 校验五类问题，任一不通过即中止发布：
 *   1. 包元数据完整性与版本号格式
 *   2. 技能清单与实际目录一致，SKILL.md 必备字段齐全
 *   3. 敏感信息扫描（密钥 / 私钥 / 凭据赋值）
 *   4. 发布白名单安全性（防止把工程文件带进包）
 *   5. 中英文 README 结构同步（见 check-readme-sync.mjs）
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { checkReadmeSync } from './check-readme-sync.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const errors = [];
const warnings = [];
const passes = [];

const OK = (m) => passes.push(m);
const FAIL = (m) => errors.push(m);
const WARN = (m) => warnings.push(m);

const read = (p) => fs.readFileSync(p, 'utf8');
const exists = (p) => fs.existsSync(p);

// ---------- 1. 包元数据 ----------
const pkgPath = path.join(ROOT, 'package.json');
if (!exists(pkgPath)) {
  FAIL('package.json 不存在');
  report();
  process.exit(1);
}
const pkg = JSON.parse(read(pkgPath));

const REQUIRED = ['name', 'version', 'description', 'keywords', 'author', 'license', 'repository', 'files', 'engines'];
for (const key of REQUIRED) {
  if (!pkg[key]) FAIL(`package.json 缺少必填字段：${key}`);
}
if (pkg.name && !/^(@[a-z0-9-~][a-z0-9-._~]*\/)?[a-z0-9-~][a-z0-9-._~]*$/.test(pkg.name)) {
  FAIL(`包名不符合 npm 规范：${pkg.name}`);
}
if (pkg.version && !/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(pkg.version)) {
  FAIL(`版本号不符合语义化版本规范：${pkg.version}`);
}
if (pkg.name?.startsWith('@') && pkg.publishConfig?.access !== 'public') {
  FAIL('scoped 包必须在 publishConfig.access 声明 public，否则发布会被拒绝');
}
if (!errors.length) OK(`包元数据完整（${pkg.name} v${pkg.version}）`);

// ---------- 2. 发布白名单安全性 ----------
const files = Array.isArray(pkg.files) ? pkg.files : [];
const FORBIDDEN = ['.git', '.workbuddy', '.codebuddy', 'node_modules', 'scripts'];
if (!files.length) {
  FAIL('files 白名单为空 —— 会把仓库全部内容打进包');
} else {
  const bad = files.filter((f) => FORBIDDEN.some((x) => f.replace(/^\.\//, '').startsWith(x)));
  if (bad.length) FAIL(`files 白名单包含不应发布的内容：${bad.join('、')}`);
  else OK(`发布白名单 ${files.length} 项，未包含工程文件`);
}
if (!exists(path.join(ROOT, '.npmignore'))) WARN('缺少 .npmignore，白名单被误改时无二次兜底');

// ---------- 3. 技能清单与 SKILL.md ----------
const skills = Array.isArray(pkg.skills) ? pkg.skills : [];
if (!skills.length) FAIL('package.json 的 skills 清单为空');

// 仓库根即技能根：技能目录直接平铺在根下，排除工程目录
const RESERVED = new Set(['node_modules', 'bin', 'scripts', 'docs']);
const diskSkills = fs.readdirSync(ROOT, { withFileTypes: true })
  .filter((d) => d.isDirectory() && !d.name.startsWith('.') && !d.name.startsWith('_') && !RESERVED.has(d.name))
  .map((d) => d.name);

const declared = new Set(skills.map((s) => s.name));
const onDisk = new Set(diskSkills);

const missingOnDisk = [...declared].filter((n) => !onDisk.has(n));
const missingInPkg = [...onDisk].filter((n) => !declared.has(n));
if (missingOnDisk.length) FAIL(`清单里声明但目录不存在：${missingOnDisk.join('、')}`);
if (missingInPkg.length) FAIL(`目录存在但未登记进 package.json skills 清单：${missingInPkg.join('、')}`);

for (const s of skills) {
  if (!s.name || !s.description || !s.path) {
    FAIL(`技能条目字段不全（需 name / description / path）：${JSON.stringify(s.name || s.path || s)}`);
    continue;
  }
  const dir = path.join(ROOT, s.path);
  if (!exists(dir)) {
    FAIL(`${s.name}：路径不存在 ${s.path}`);
    continue;
  }
  const skillMd = path.join(dir, 'SKILL.md');
  if (!exists(skillMd)) {
    FAIL(`${s.name}：缺少 SKILL.md`);
    continue;
  }
  const head = read(skillMd).split('\n').slice(0, 40).join('\n');
  for (const field of ['name', 'description']) {
    if (!new RegExp(`^${field}:\\s*\\S`, 'm').test(head)) {
      FAIL(`${s.name}：SKILL.md frontmatter 缺少 ${field}`);
    }
  }
  // 平台约束：只允许单层子目录
  const nested = fs.readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('.'))
    .some((d) => fs.readdirSync(path.join(dir, d.name), { withFileTypes: true }).some((x) => x.isDirectory()));
  if (nested) WARN(`${s.name}：存在二级子目录，部分技能平台只识别单层结构`);
}
if (skills.length && !errors.some((e) => e.includes('SKILL.md') || e.includes('目录'))) {
  OK(`技能清单与目录一致（${skills.length} 个技能，SKILL.md 字段齐全）`);
}

// files 白名单必须覆盖全部技能目录，否则发布时会漏发
const uncovered = [...onDisk].filter((n) => !files.some((f) => f.replace(/\/$/, '') === n));
if (uncovered.length) {
  FAIL(`以下技能目录未列入 files 白名单，发布会漏发：${uncovered.join('、')}`);
} else if (onDisk.size) {
  OK(`files 白名单覆盖全部 ${onDisk.size} 个技能目录`);
}

// ---------- 4. 敏感信息扫描 ----------
const PATTERNS = [
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, '私钥文件内容'],
  [/\bAKIA[0-9A-Z]{16}\b/, 'AWS Access Key'],
  [/\bLTAI[A-Za-z0-9]{12,}\b/, '阿里云 AccessKey'],
  [/\bAKID[A-Za-z0-9]{16,}\b/, '腾讯云 SecretId'],
  [/\bsk-[A-Za-z0-9]{20,}\b/, 'OpenAI 风格密钥'],
  [/\bghp_[A-Za-z0-9]{30,}\b/, 'GitHub Token'],
  [/\bgithub_pat_[A-Za-z0-9_]{20,}\b/, 'GitHub 细粒度 Token'],
  [/\bapp_?secret["'\s:=]+[A-Za-z0-9]{24,}/i, '明文 AppSecret 赋值'],
  [/\b(password|passwd|pwd)["'\s:=]+[^\s"']{8,}/i, '明文口令赋值'],
];
const SCAN_EXT = new Set(['.md', '.json', '.js', '.mjs', '.cjs', '.py', '.sh', '.yml', '.yaml', '.txt', '.html']);
let hitCount = 0;

(function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git' || entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
    } else if (SCAN_EXT.has(path.extname(entry.name).toLowerCase())) {
      const text = read(full);
      text.split('\n').forEach((line, i) => {
        // 跳过明显是文档说明的行（描述凭据处理规范而非真实凭据）
        if (/脱敏|不入库|绝不|请勿|不得|禁止写入|示例|placeholder|your[_-]?key|xxx/i.test(line)) return;
        for (const [re, label] of PATTERNS) {
          if (re.test(line)) {
            hitCount += 1;
            FAIL(`${path.relative(ROOT, full)}:${i + 1} 疑似${label}：${line.trim().slice(0, 80)}`);
          }
        }
      });
    }
  }
})(ROOT);

if (!hitCount) OK('敏感信息扫描：未发现密钥 / 私钥 / 凭据明文');

// ---------- 5. 中英文 README 同步 ----------
const readmeSync = checkReadmeSync();
for (const note of readmeSync.notes) OK(note);
for (const issue of readmeSync.issues) FAIL(issue);

// ---------- 报告 ----------
function report() {
  const line = '─'.repeat(58);
  console.log(`\n${line}`);
  console.log('  发布前校验 · @fore-auto/skills');
  console.log(line);
  for (const p of passes) console.log(`  ✓ ${p}`);
  for (const w of warnings) console.log(`  ! ${w}`);
  for (const e of errors) console.log(`  ✗ ${e}`);
  console.log(line);
  if (errors.length) {
    console.log(`  结果：不通过（${errors.length} 项错误${warnings.length ? `，${warnings.length} 项警告` : ''}）\n`);
  } else {
    console.log(`  结果：通过${warnings.length ? `（${warnings.length} 项警告）` : ''}\n`);
  }
}

report();
process.exit(errors.length ? 1 : 0);
