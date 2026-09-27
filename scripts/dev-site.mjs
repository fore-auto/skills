#!/usr/bin/env node
/**
 * 本地预览 —— 在不上线的前提下复刻 Vercel 的路由行为
 *
 *   node scripts/dev-site.mjs            # http://127.0.0.1:4321
 *   PORT=8080 node scripts/dev-site.mjs
 *
 * 复刻要点（与线上一致才测得准）：
 *   - 静态资源只来自 dist/（对应 vercel.json 的 outputDirectory）
 *   - /api/<name> 映射到 api/<name>.js，以 CommonJS 调用
 *   - api/ 下以 "_" 开头的文件是内部工具，不对外暴露
 *
 * 先跑 `npm run build` 生成 dist/，再启动本脚本。
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(ROOT, 'dist');
const PORT = Number(process.env.PORT || 4321);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

if (!fs.existsSync(path.join(DIST, 'index.html'))) {
  console.error('✗ dist/index.html 不存在，请先执行：npm run build');
  process.exit(1);
}

const handlerCache = new Map();
function loadHandler(name) {
  if (!handlerCache.has(name)) {
    const file = path.join(ROOT, 'api', `${name}.js`);
    if (!fs.existsSync(file)) return null;
    handlerCache.set(name, require(file));
  }
  return handlerCache.get(name);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

  // ── /api/* ──
  if (url.pathname.startsWith('/api/')) {
    const name = url.pathname.slice('/api/'.length);
    if (!name || name.startsWith('_') || name.includes('/') || name.includes('..')) {
      res.statusCode = 404;
      return res.end('Not found');
    }
    const handler = loadHandler(name);
    if (!handler) {
      res.statusCode = 404;
      return res.end('Not found');
    }
    try {
      return handler(req, res);
    } catch (e) {
      res.statusCode = 500;
      return res.end(JSON.stringify({ error: String(e && e.message) }));
    }
  }

  // ── 静态资源（仅 dist/）──
  let rel = decodeURIComponent(url.pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  const file = path.join(DIST, rel);
  if (!file.startsWith(DIST)) {
    res.statusCode = 403;
    return res.end('Forbidden');
  }
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.statusCode = 404;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('404 Not found');
  }
  const body = fs.readFileSync(file);
  res.statusCode = 200;
  res.setHeader('Content-Type', MIME[path.extname(file).toLowerCase()] || 'application/octet-stream');
  res.setHeader('Content-Length', body.length);
  res.end(body);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('');
  console.log(`  本地预览：http://127.0.0.1:${PORT}`);
  console.log(`  静态目录：dist/   函数目录：api/`);
  console.log('');
});
