#!/usr/bin/env bash
#
# 发布脚本 —— 一条命令完成「校验 → 提版 → 发布 → 推送」
#
# 用法：
#   ./scripts/publish.sh            # 补丁版 1.0.0 → 1.0.1
#   ./scripts/publish.sh minor      # 次版本 1.0.0 → 1.1.0
#   ./scripts/publish.sh major      # 主版本 1.0.0 → 2.0.0
#   ./scripts/publish.sh --dry-run  # 只校验与试打包，不真正发布
#
# 前置条件：
#   npm 已登录且对 @fore-auto 作用域有发布权限：npm login

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

BUMP="patch"
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    patch|minor|major) BUMP="$arg" ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数：$arg（可用：patch / minor / major / --dry-run）" >&2; exit 1 ;;
  esac
done

echo ""
echo "── 发布 @fore-auto/skills ──"
echo "目录：$ROOT"
echo "提版：$BUMP$([ "$DRY_RUN" = 1 ] && echo "（试运行，不实际发布）")"
echo ""

# 1. 工作区必须干净，避免把未提交改动一起发出去
if [ -n "$(git status --porcelain)" ]; then
  echo "✗ 工作区有未提交改动，请先提交或暂存：" >&2
  git status --short >&2
  exit 1
fi
echo "✓ 工作区干净"

# 2. 分支检查
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "! 当前分支为 $BRANCH（非 main），请确认是否继续" >&2
fi

# 3. 发布前校验
npm run check

# 4. 试打包，人工确认包内容
echo ""
echo "── 包内容预览 ──"
npm pack --dry-run 2>&1 | tail -25

if [ "$DRY_RUN" = 1 ]; then
  echo ""
  echo "✓ 试运行结束，未执行发布。"
  exit 0
fi

# 5. 确认发布
echo ""
printf "确认发布？输入 yes 继续："
read -r CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "已取消。"
  exit 0
fi

# 6. npm 登录状态
if ! npm whoami >/dev/null 2>&1; then
  echo "✗ 未登录 npm，请先执行：npm login" >&2
  exit 1
fi
echo "✓ npm 已登录：$(npm whoami)"

# 7. 提版 + 发布 + 推送
NEW_VERSION="$(npm version "$BUMP" -m "chore(release): v%s")"
echo "✓ 版本已更新：$NEW_VERSION"

npm publish
echo "✓ 已发布到 npm"

git push origin "$BRANCH" --follow-tags
echo "✓ 代码与 tag 已推送"

echo ""
echo "完成：https://www.npmjs.com/package/@fore-auto/skills"
echo "使用：npx @fore-auto/skills"
