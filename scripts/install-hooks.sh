#!/usr/bin/env bash
#
# 安装 git hooks（把 scripts/hooks/ 下的钩子链接到 .git/hooks/）
#
# 由 `npm install` 经 prepare 自动触发，也可手动执行：bash scripts/install-hooks.sh
# 非 git 环境（例如 npm 打包时）会静默跳过，不影响发布。

set -uo pipefail

cd "$(dirname "$0")/.." || exit 0

HOOK_DIR=".git/hooks"
SRC_DIR="scripts/hooks"

if [ ! -d "$HOOK_DIR" ]; then
  echo "install-hooks: 当前不是 git 仓库，跳过（打包/安装场景正常）"
  exit 0
fi

if [ ! -d "$SRC_DIR" ]; then
  echo "install-hooks: 未找到 $SRC_DIR，跳过"
  exit 0
fi

INSTALLED=0
for SRC in "$SRC_DIR"/*; do
  [ -f "$SRC" ] || continue
  NAME="$(basename "$SRC")"
  DST="$HOOK_DIR/$NAME"

  # 已有非本项目安装的同名钩子 → 先备份，避免覆盖别人的配置
  if [ -e "$DST" ] && ! grep -q "check-readme-sync\|install-hooks" "$DST" 2>/dev/null; then
    BAK="$DST.bak.$(date +%Y%m%d%H%M%S)"
    cp "$DST" "$BAK" && echo "install-hooks: 已备份原 $NAME → $BAK"
  fi

  cp "$SRC" "$DST" && chmod +x "$DST" && INSTALLED=$((INSTALLED + 1))
  echo "install-hooks: 已安装 $NAME"
done

if [ "$INSTALLED" -gt 0 ]; then
  echo "install-hooks: 完成（$INSTALLED 个钩子）"
else
  echo "install-hooks: 没有可安装的钩子"
fi

exit 0
