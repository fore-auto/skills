/**
 * Vercel Node Function —— 动态打包技能目录为 zip
 *
 *   GET /api/zip?skill=auto-geo      → 下载 auto-geo.zip
 *   GET /api/zip?skill=all           → 下载 fore-auto-skills-all.zip（全部技能）
 *   GET /api/zip?diag=1              → 诊断：本次部署实际能看到哪些技能目录
 *
 * 运行方式：CommonJS（仓库 package.json 顶层没有 "type" 字段）。
 * 白名单来源：磁盘上带 SKILL.md 的顶层目录 —— 不存在清单漂移的可能。
 * 依赖：仅 Node 内置模块。
 */

const path = require('node:path');
const { listSkills, zipSkill, zipAll } = require('./_zip.js');

// 源码目录候选：Vercel 部署后为 /var/task（进程 cwd）；本地直跑时回退到仓库根
const CANDIDATES = [
  process.env.SKILLS_ROOT,
  process.cwd(),
  path.resolve(__dirname, '..'),
  path.resolve(process.cwd(), '..'),
].filter(Boolean);

let cachedRoot = null;
function resolveRoot() {
  if (cachedRoot) return cachedRoot;
  for (const dir of CANDIDATES) {
    try {
      if (listSkills(dir).length) {
        cachedRoot = dir;
        return dir;
      }
    } catch {
      /* 该候选目录不可读，继续试下一个 */
    }
  }
  cachedRoot = process.cwd();
  return cachedRoot;
}

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload, null, 2), 'utf8');
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Length', body.length);
  res.setHeader('Cache-Control', 'no-store');
  res.end(body);
}

module.exports = function handler(req, res) {
  const started = Date.now();
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const root = resolveRoot();
  const names = listSkills(root);

  // ── 诊断入口：首次部署时用来确认 includeFiles 是否生效 ──
  if (url.searchParams.get('diag') === '1') {
    return sendJson(res, 200, {
      cwd: process.cwd(),
      resolvedRoot: root,
      skillCount: names.length,
      skills: names,
      node: process.version,
    });
  }

  const skill = (url.searchParams.get('skill') || '').trim();

  if (!skill) {
    return sendJson(res, 400, {
      error: '缺少 skill 参数',
      usage: '/api/zip?skill=<name> 或 /api/zip?skill=all',
      available: names,
    });
  }

  // 白名单校验：必须精确命中磁盘上真实存在的技能目录。
  // 由于只在 names 里查找、且 names 来自 fs.readdirSync，任何含 "/" 或 ".." 的输入都不可能命中。
  const wantAll = skill === 'all';
  if (!wantAll && !names.includes(skill)) {
    return sendJson(res, 404, { error: `未知技能：${skill}`, available: names });
  }

  let buffer;
  let filename;
  try {
    if (wantAll) {
      const r = zipAll(root, names);
      buffer = r.buffer;
      filename = 'fore-auto-skills-all.zip';
    } else {
      const r = zipSkill(root, skill);
      buffer = r.buffer;
      filename = `${skill}.zip`;
    }
  } catch (e) {
    return sendJson(res, 500, { error: `打包失败：${e.message}` });
  }

  res.statusCode = 200;
  res.setHeader('Content-Type', 'application/zip');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  res.setHeader('Content-Length', buffer.length);
  // 纯函数式产出：同一份源码字节恒定，交给 CDN 长缓存
  res.setHeader('Cache-Control', 'public, max-age=300, s-maxage=86400, stale-while-revalidate=604800');
  res.setHeader('X-Archive-Bytes', String(buffer.length));
  res.setHeader('X-Archive-Ms', String(Date.now() - started));

  if (req.method === 'HEAD') {
    res.removeHeader('Content-Length');
    return res.end();
  }
  return res.end(buffer);
};
