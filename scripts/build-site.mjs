#!/usr/bin/env node
/**
 * 站点构建 —— 生成 skills.fore.vip 的静态产物到 dist/
 *
 *   node scripts/build-site.mjs
 *
 * 产出：
 *   dist/index.html    下载首页（点击卡片即下载对应 zip）
 *   dist/skills.json   机器可读的技能清单（含真实包体积）
 *   dist/llms.txt      给 AI 引擎的说明文件
 *   dist/robots.txt    /  dist/sitemap.xml
 *
 * 设计约束：
 *   - 零第三方依赖，只用 Node 内置模块 + 仓库内的 api/_zip.js（与线上打包同一份实现）
 *   - 单一事实源：技能名单与文案取自 package.json 的 skills[]，版本号取自各技能 SKILL.md frontmatter
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { collectEntries, buildZip, listSkills } = require('../api/_zip.js');

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(ROOT, 'dist');
const SITE = 'https://skills.fore.vip';

// ── 读取 package.json 清单 ──────────────────────────────
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const manifest = pkg.skills || [];

// ── 读取 SKILL.md frontmatter ───────────────────────────
function frontmatter(file) {
  const text = fs.readFileSync(file, 'utf8');
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return {};
  const out = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!kv) continue;
    let v = kv[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    out[kv[1]] = v;
  }
  return out;
}

const CATEGORY_LABEL = {
  productivity: '效率',
  web: '建站',
  marketing: '营销',
  'iot-control': '硬件',
  'system-tools': '系统',
  sales: '销售',
  media: '媒体',
};

// ── 组装数据：版本、文件数、原始体积、zip 体积 ────────────
const skills = manifest.map((s) => {
  const dir = path.join(ROOT, s.name);
  const fm = fs.existsSync(path.join(dir, 'SKILL.md')) ? frontmatter(path.join(dir, 'SKILL.md')) : {};
  const entries = collectEntries(dir, s.name);
  const files = entries.filter((e) => !e.dir);
  const rawBytes = files.reduce((n, f) => n + f.data.length, 0);
  const zipBytes = buildZip(entries).length;

  const version = fm.version || s.version || '';
  if (fm.version && s.version && fm.version !== s.version) {
    console.warn(`  ! 版本不一致：${s.name} — SKILL.md ${fm.version} / package.json ${s.version}（页面按 SKILL.md 显示）`);
  }

  return {
    name: s.name,
    displayName: s.displayName || fm.displayName || s.name,
    description: s.description || fm.description || '',
    category: s.category || fm.category || '',
    categoryLabel: CATEGORY_LABEL[s.category || fm.category] || (s.category || fm.category || ''),
    version,
    files: files.length,
    rawBytes,
    zipBytes,
    download: `/api/zip?skill=${encodeURIComponent(s.name)}`,
    filename: `${s.name}.zip`,
  };
});

// 磁盘上存在但未登记进清单的技能 → 显式告警，避免首页漏列
const onDisk = listSkills(ROOT);
const missing = onDisk.filter((n) => !skills.some((s) => s.name === n));
if (missing.length) console.warn(`  ! 未登记进 package.json skills[]，首页不会展示：${missing.join('、')}`);

const allEntries = [];
for (const s of onDisk) {
  allEntries.push({ name: `${s}/`, dir: true });
  collectEntries(path.join(ROOT, s), s, allEntries);
}
const allZipBytes = buildZip(allEntries).length;
const totalFiles = skills.reduce((n, s) => n + s.files, 0);
const totalRaw = skills.reduce((n, s) => n + s.rawBytes, 0);

// ── 工具 ────────────────────────────────────────────────
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const kb = (n) => (n / 1024 >= 100 ? `${Math.round(n / 1024)} KB` : `${(n / 1024).toFixed(1)} KB`);
const BUILT = new Date().toISOString().slice(0, 10);

// ── 首页 ────────────────────────────────────────────────
const cards = skills
  .map(
    (s) => `      <a class="card" href="${s.download}" download>
        <span class="card-line"></span>
        <div class="card-head">
          <span class="cat">${esc(s.categoryLabel)}</span>
          <span class="ver">v${esc(s.version)}</span>
        </div>
        <h3>${esc(s.displayName)}</h3>
        <p>${esc(s.description)}</p>
        <div class="card-foot">
          <span class="meta"><b class="fname">${esc(s.filename)}</b><span class="fdim">${kb(s.zipBytes)} · ${s.files} 个文件</span></span>
          <span class="go">下载</span>
        </div>
      </a>`
  )
  .join('\n');

const indexHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>AUTO Skills - 现成技能，下载即用</title>
<meta name="description" content="AUTO 技能家族下载站：${skills.length} 个可直接安装的 AI 技能包，覆盖建站、GEO、硬件控制、电脑优化、视频处理、客户挖掘。点击卡片下载 zip，解压到技能目录即可使用。">
<meta name="theme-color" content="#0b0b0f">
<link rel="icon" type="image/png" href="https://auto.fore.vip/logo-mark.png">
<link rel="canonical" href="${SITE}/">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
<meta property="og:title" content="AUTO Skills - 现成技能，下载即用">
<meta property="og:description" content="${skills.length} 个可直接安装的 AI 技能包，点击卡片下载 zip，解压到技能目录即可使用。">
<meta property="og:type" content="website">
<meta property="og:url" content="${SITE}/">
<meta property="og:site_name" content="AUTO Skills">
<meta property="og:locale" content="zh_CN">
<meta property="og:image" content="https://auto.fore.vip/og-cover.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"CollectionPage","name":"AUTO Skills","url":"${SITE}/","inLanguage":"zh-CN","publisher":{"@type":"Organization","name":"前凌智选","url":"https://auto.fore.vip/"}}
</script>
<style>
:root{
  --brand:#e53e3e; --brand-soft:#ff6b5e; --brand-dim:rgba(229,62,62,.14);
  --bg:#0b0b0f; --bg-2:#0f0f15; --card:#15151d; --card-2:#1b1b24;
  --line:rgba(255,255,255,.075); --line-2:rgba(255,255,255,.13);
  --text:#f4f4f7; --sub:#a4a4b2; --muted:#6d6d7c;
  --r:16px; --r-sm:11px; --max:1140px;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.75;letter-spacing:.012em}
a{color:inherit;text-decoration:none}
.wrap{max-width:var(--max);margin:0 auto;padding:0 22px}
header{border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(11,11,15,.86);backdrop-filter:blur(12px);z-index:9}
.hd{display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px}
.brand{display:flex;align-items:center;gap:9px;font-size:15px;font-weight:500;letter-spacing:.02em}
.dot{width:9px;height:9px;border-radius:50%;background:var(--brand);display:inline-block}
.brand em{color:var(--muted);font-style:normal;font-weight:400}
.btn{display:inline-flex;align-items:center;gap:7px;padding:8px 15px;border-radius:var(--r-sm);border:1px solid var(--line-2);background:var(--card);font-size:13.5px;color:var(--text);transition:.16s}
.btn:hover{border-color:var(--brand);color:#fff;background:var(--brand-dim)}
.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}
.btn.primary:hover{background:var(--brand-soft);border-color:var(--brand-soft)}
.hero{padding:64px 0 40px}
h1{font-size:clamp(28px,5vw,42px);line-height:1.24;font-weight:500;letter-spacing:-.01em}
h1 em{color:var(--brand);font-style:normal}
.lede{margin-top:16px;color:var(--sub);max-width:620px;font-size:15.5px}
.kpis{display:flex;flex-wrap:wrap;gap:26px;margin-top:26px;color:var(--muted);font-size:13.5px}
.kpis b{color:var(--text);font-weight:500}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px;padding:8px 0 20px}
.card{position:relative;display:flex;flex-direction:column;gap:10px;padding:22px 22px 18px;border:1px solid var(--line);border-radius:var(--r);background:var(--card);overflow:hidden;transition:.18s}
.card-line{position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--brand);opacity:.35;transition:.18s}
.card:hover{transform:translateY(-2px);border-color:var(--line-2);background:var(--card-2)}
.card:hover .card-line{opacity:1}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.cat{font-size:11.5px;color:var(--brand);border:1px solid var(--brand-dim);background:var(--brand-dim);border-radius:999px;padding:2px 9px;letter-spacing:.04em}
.ver{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.card h3{font-size:17px;font-weight:500}
.card p{color:var(--sub);font-size:13.5px;line-height:1.65;flex:1}
.card-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:2px}
.meta{display:flex;flex-direction:column;gap:1px;flex:1 1 auto;min-width:0;font-family:var(--mono);font-size:11.5px;line-height:1.55}
.fname{color:var(--sub);font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fdim{color:var(--muted)}
.go{font-size:13px;color:var(--brand);white-space:nowrap}
.card:hover .go{color:var(--brand-soft)}
.sec{padding:38px 0}
.sec h2{font-size:20px;font-weight:500;margin-bottom:6px}
.sec .sub{color:var(--sub);font-size:14px;margin-bottom:20px}
.panel{border:1px solid var(--line);border-radius:var(--r);background:var(--bg-2);padding:22px}
.cmd{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#0a0a0e;border:1px solid var(--line);border-radius:var(--r-sm);padding:12px 14px;font-family:var(--mono);font-size:13px;overflow-x:auto}
.cmd span{white-space:pre;color:var(--text);opacity:.92}
.copy{border:1px solid var(--line-2);background:transparent;color:var(--sub);font-size:12px;padding:4px 10px;border-radius:7px;cursor:pointer;font-family:var(--sans);flex:none}
.copy:hover{border-color:var(--brand);color:var(--brand)}
.steps{margin:16px 0 0;padding-left:20px;color:var(--sub);font-size:14px}
.steps li{margin-bottom:7px}
.steps code{font-family:var(--mono);font-size:12.5px;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1px 6px;color:var(--text)}
footer{border-top:1px solid var(--line);margin-top:26px;padding:26px 0 44px;color:var(--muted);font-size:13px}
.foot{display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between}
.foot a:hover{color:var(--brand)}
@media (max-width:560px){.hero{padding:40px 0 28px}.card{padding:18px}.meta{font-size:11px}}
</style>
</head>
<body>
<header>
  <div class="wrap hd">
    <a class="brand" href="/"><span class="dot"></span>AUTO <em>Skills</em></a>
    <a class="btn primary" href="/api/zip?skill=all" download>下载全部 · ${kb(allZipBytes)}</a>
  </div>
</header>

<main class="wrap">
  <section class="hero">
    <h1>现成技能，<em>下载即用</em></h1>
    <p class="lede">${skills.length} 个可直接安装的 AI 技能包。点击卡片下载 zip，解压到技能目录就能用；也可以直接用 npx 一键安装。</p>
    <div class="kpis">
      <span><b>${skills.length}</b> 个技能</span>
      <span><b>${kb(totalRaw)}</b> 源码</span>
      <span><b>${totalFiles}</b> 个文件</span>
      <span><b>${kb(allZipBytes)}</b> 全量包</span>
    </div>
  </section>

  <div class="grid">
${cards}
  </div>

  <section class="sec">
    <h2>安装</h2>
    <p class="sub">需要支持技能（Skill）的 AI 助手客户端；npx 方式另需 Node.js 18 或更高版本。</p>
    <div class="panel">
      <div class="cmd"><span>npx @fore-auto/skills add auto-geo</span><button class="copy" data-copy="npx @fore-auto/skills add auto-geo">复制</button></div>
      <ol class="steps">
        <li>下载任意卡片的 zip，解压得到 <code>技能名/</code> 目录（内含 <code>SKILL.md</code>）。</li>
        <li>把整个目录放进 <code>~/.workbuddy/skills/</code>（只在当前项目生效则放 <code>.workbuddy/skills/</code>）。</li>
        <li>在 AI 助手里直接说需求，例如「帮我优化下电脑」「把这个视频压小点」。</li>
      </ol>
    </div>
  </section>
</main>

<footer>
  <div class="wrap foot">
    <span>© ${BUILT.slice(0, 4)} fore.vip · MIT License</span>
    <span>
      <a href="https://auto.fore.vip">auto.fore.vip</a> ·
      <a href="https://github.com/fore-auto/skills">GitHub</a> ·
      <a href="mailto:hi@fore.vip">hi@fore.vip</a>
    </span>
  </div>
</footer>

<script>
document.querySelectorAll('.copy').forEach(function (b) {
  b.addEventListener('click', function () {
    var text = b.getAttribute('data-copy');
    var done = function () { b.textContent = '已复制'; setTimeout(function () { b.textContent = '复制'; }, 1400); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, done);
    } else {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(t); done();
    }
  });
});
</script>
</body>
</html>
`;

// ── skills.json / llms.txt / robots.txt / sitemap.xml ───
const skillsJson = {
  site: SITE,
  generatedAt: new Date().toISOString(),
  totalSkills: skills.length,
  allDownload: `/api/zip?skill=all`,
  allBytes: allZipBytes,
  skills: skills.map((s) => ({
    name: s.name,
    displayName: s.displayName,
    description: s.description,
    category: s.category,
    version: s.version,
    files: s.files,
    bytes: s.zipBytes,
    download: s.download,
  })),
};

const listLines = skills.map((s) => `- ${s.displayName}（${s.name}，v${s.version}）：${s.description} 下载 ${SITE}${s.download}`).join('\n');

const llmsTxt = `# AUTO Skills

> AUTO 技能家族的可下载技能包集合，${skills.length} 个技能，面向支持 Skill 的 AI 助手客户端。

站点：${SITE}
全量包：${SITE}/api/zip?skill=all （${kb(allZipBytes)}）
清单接口：${SITE}/skills.json

## 技能列表

${listLines}

## 安装方式

1. 直接下载：打开 ${SITE} ，点击任意技能卡片即下载对应 zip，解压后放入 ~/.workbuddy/skills/（或项目的 .workbuddy/skills/）。
2. 命令行：\`npx @fore-auto/skills add <技能名>\`（需 Node.js 18+）。

## 说明

- 每个 zip 的根目录为技能名目录，内含 SKILL.md 与 references 等文件。
- 技能只在用户主动要求时执行操作；涉及删除或修改系统设置会先征询。
- 出品：前凌智选 / fore.vip
`;

const robotsTxt = `User-agent: *
Allow: /

Sitemap: ${SITE}/sitemap.xml
`;

const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${SITE}/</loc>
    <lastmod>${BUILT}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
`;

// ── 落盘 ────────────────────────────────────────────────
fs.rmSync(DIST, { recursive: true, force: true });
fs.mkdirSync(DIST, { recursive: true });
fs.writeFileSync(path.join(DIST, 'index.html'), indexHtml);
fs.writeFileSync(path.join(DIST, 'skills.json'), JSON.stringify(skillsJson, null, 2) + '\n');
fs.writeFileSync(path.join(DIST, 'llms.txt'), llmsTxt);
fs.writeFileSync(path.join(DIST, 'robots.txt'), robotsTxt);
fs.writeFileSync(path.join(DIST, 'sitemap.xml'), sitemapXml);

console.log('');
console.log('── 构建 skills.fore.vip ──');
console.log(`  技能 ${skills.length} 个 / 源码 ${kb(totalRaw)} / ${totalFiles} 文件`);
for (const s of skills) console.log(`  · ${s.name.padEnd(24)} v${s.version.padEnd(7)} ${kb(s.zipBytes).padStart(8)}  ${s.files} 文件`);
console.log(`  全量包 ${kb(allZipBytes)}`);
console.log(`  产出 dist/：${fs.readdirSync(DIST).sort().join('、')}`);
console.log('');
