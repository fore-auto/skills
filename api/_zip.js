/**
 * 零依赖 ZIP 组装器（CJS，供 Vercel Function 与本地构建脚本共用）
 *
 * 只依赖 Node 内置模块：node:fs / node:path / node:zlib
 * 文件名以 "_" 开头 → Vercel 不会把它当成一个 Function（见官方忽略规则）。
 */

const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

// ── CRC32 ────────────────────────────────────────────────
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

// 固定 DOS 时间戳 → 同一份源码每次产出的 zip 字节完全一致（可复现、便于 CDN 校验）
const DOS_TIME = 0x2821;
const DOS_DATE = 0x2821;

const SKIP = new Set(['.DS_Store', 'Thumbs.db', 'Desktop.ini', '__MACOSX']);

// 平台安装元数据（ownerId / slug / installedAt / pricing 等）属于本机状态，不进交付包：
// 用户从 zip 安装时带着别人的 ownerId 与 installedAt 会污染平台的技能归属记录。
const SKIP_META = /^_.*meta\.json$/i;

function shouldSkip(name) {
  return SKIP.has(name) || SKIP_META.test(name) || name.startsWith('.');
}

/**
 * 递归收集目录内容，保持相对结构；目录条目排在文件之前（与 zip CLI 行为一致）
 * @returns {Array<{name:string, dir?:boolean, data?:Buffer}>}
 */
function collectEntries(diskDir, zipRoot, out = []) {
  const items = fs.readdirSync(diskDir, { withFileTypes: true }).sort((a, b) => {
    if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  for (const e of items) {
    if (shouldSkip(e.name)) continue;
    const full = path.join(diskDir, e.name);
    const rel = zipRoot ? `${zipRoot}/${e.name}` : e.name;
    if (e.isDirectory()) {
      out.push({ name: `${rel}/`, dir: true });
      collectEntries(full, rel, out);
    } else if (e.isFile()) {
      out.push({ name: rel, data: fs.readFileSync(full) });
    }
  }
  return out;
}

/** 把条目列表组装成标准 ZIP Buffer */
function buildZip(entries) {
  const locals = [];
  const central = [];
  let offset = 0;

  for (const it of entries) {
    const nameBuf = Buffer.from(it.name, 'utf8');
    const raw = it.dir ? Buffer.alloc(0) : it.data;
    const comp = raw.length ? zlib.deflateRawSync(raw, { level: 9 }) : Buffer.alloc(0);
    const crc = raw.length ? crc32(raw) : 0;
    const method = raw.length ? 8 : 0;

    const lh = Buffer.alloc(30);
    lh.writeUInt32LE(0x04034b50, 0);
    lh.writeUInt16LE(20, 4);
    lh.writeUInt16LE(0x0800, 6); // 文件名按 UTF-8 解读
    lh.writeUInt16LE(method, 8);
    lh.writeUInt16LE(DOS_TIME, 10);
    lh.writeUInt16LE(DOS_DATE, 12);
    lh.writeUInt32LE(crc, 14);
    lh.writeUInt32LE(comp.length, 18);
    lh.writeUInt32LE(raw.length, 22);
    lh.writeUInt16LE(nameBuf.length, 26);
    lh.writeUInt16LE(0, 28);

    const ch = Buffer.alloc(46);
    ch.writeUInt32LE(0x02014b50, 0);
    ch.writeUInt16LE(20, 4);
    ch.writeUInt16LE(20, 6);
    ch.writeUInt16LE(0x0800, 8);
    ch.writeUInt16LE(method, 10);
    ch.writeUInt16LE(DOS_TIME, 12);
    ch.writeUInt16LE(DOS_DATE, 14);
    ch.writeUInt32LE(crc, 16);
    ch.writeUInt32LE(comp.length, 20);
    ch.writeUInt32LE(raw.length, 24);
    ch.writeUInt16LE(nameBuf.length, 28);
    ch.writeUInt32LE(it.dir ? 0x10 : 0, 38);
    ch.writeUInt32LE(offset, 42);

    locals.push(lh, nameBuf, comp);
    central.push(ch, nameBuf);
    offset += lh.length + nameBuf.length + comp.length;
  }

  const cdBuf = Buffer.concat(central);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(cdBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);

  return Buffer.concat([...locals, cdBuf, eocd]);
}

/**
 * 列出「技能目录」：顶层目录中带 SKILL.md 的即视为技能。
 * 不用清单文件，避免清单与磁盘漂移；目录内没有 SKILL.md 的一律不算。
 */
function listSkills(rootDir) {
  return fs
    .readdirSync(rootDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('.') && !d.name.startsWith('_'))
    .map((d) => d.name)
    .filter((n) => fs.existsSync(path.join(rootDir, n, 'SKILL.md')))
    .sort();
}

/** 打包单个技能，返回 { buffer, entries } */
function zipSkill(rootDir, name) {
  const dir = path.join(rootDir, name);
  const entries = collectEntries(dir, name);
  return { buffer: buildZip(entries), entries };
}

/** 打包全部技能为一个 zip */
function zipAll(rootDir, names, rootName = 'fore-auto-skills-all') {
  const entries = [];
  for (const n of names) {
    entries.push({ name: `${n}/`, dir: true });
    collectEntries(path.join(rootDir, n), n, entries);
  }
  return { buffer: buildZip(entries), entries };
}

module.exports = { crc32, collectEntries, buildZip, listSkills, zipSkill, zipAll };
