# 需求发布服务 · 调用速查

供 SKILL.md 的 N0（前置确认）、N3（同名预检）、N4（写入）、N5（回执）与「我自己发布的需求」使用。**只写调用方需要知道的事**：发什么、拿什么、出错怎么办。

**服务定位**：`https://mcp.fore.vip/crm` —— 联盟共享的客户 / 需求池。需求发进去以后，**所有联盟会员**在客户控制台（https://fore.vip/web/crm）的「全域」里都能看到这条记录的「需求」标记，供方据此对接你。

> **与「找客户」技能的核心差别**：那个技能落库一律 `lead`（线索）且**落库前不查库**；本技能落库**必须显式写 `need`（需求）**，且**写之前必须先做同名预检**（见第四节）。

## 一、端点

| 用途 | REST | MCP 工具名 |
|---|---|---|
| 单条发布 / 合并 | `POST /crm/save` | `save_company` |
| 批量发布 / 合并 | `POST /crm/saveMany` | `save_companies` |
| 同名预检 / 单条详情 | `POST /crm/detail` | `get_company` |
| 检索（查我发布的） | `POST /crm/search` | `search_companies` |
| 更新（改我没发的） | `POST /crm/update` | `update_company` |
| 删除（撤下） | `POST /crm/delete` | `delete_company` |
| 统计 | `POST /crm/stats` | `company_stats` |
| 连通性确认 | `POST /crm/tools` | `tools/list` |

**通道按序取用**：① 运行环境已配置 crm MCP 服务 → 直接调 MCP 工具；② 否则用 HTTP 请求工具 POST 上表端点（`Content-Type: application/json`）；③ 服务不可用或没有 Key → **不落本地文件**，改出「需求卡片」（见 @need-card.md）。

## 二、字段与约束

| 字段 | 本技能怎么填 | 上限 | 说明 |
|---|---|---|---|
| `company` | **必填** | 128 | 发布主体的企业名称，工商全称优先。**去重主键，精确匹配** |
| `type` | **必须传 `need`** | 枚举 | `lead`（线索）/ `need`（需求）。**本技能唯一必须显式传的记录类型** —— 不传会被写成线索 |
| `industry` | 建议填 | 64 | 你方所在行业 |
| `product` | 建议填 | 128 | **你方自己的**品牌 / 主营产品（不是要采购的东西） |
| `contact` | 强烈建议填 | 256 | 联系方式，多值半角 `;`。**别人找到你的唯一途径** |
| `email` | 强烈建议填 | 256 | 邮箱，多值半角 `;` |
| `remark` | **必填（业务上）** | 500 | 需求正文，建议以 `[需求]` 起头 |
| `source` | 填 `用户自述·YYYY-MM-DD` | 256 | 来源·时间 |
| `status` | **不要传** | 枚举 | 新记录默认 `未接触` —— 也正是它进「全域」公开池的条件 |
| `priority` | **不要传** | 枚举 | 默认「中」；要改走 `update` 或让用户在控制台点 |
| `creator` | **不要传** | 64 | 归属，服务端按 `X-API-Key` 反查 uid 自动写入；已有归属不被覆盖 |
| `owner` | 不要传 | 128 | 负责人，采集场景的字段；发布需求用不上 |
| `heat` | **不要传** | 整数 | **火力值** —— 这条需求在同行业里的曝光排位值，越大越靠前。由用户在控制台行尾徽标上**花钱投放**写入（出价式：成本 = 该行业当前最高火力值 + 10），本技能既不能也不该写。**新发布的需求初值 `10`**（行业冷启动价）；看到别人的需求排在你前面就是它比你高 |
| `quality_score` / `report_url` / `report_time` | **不要写** | — | 由 GEO 评测自动任务回写 |

- 多值字段一律半角 `;` 分隔。
- `_id` / `create_time` / `update_time` 由服务自管，不可写入。

## 三、各方法入参与返回

| 方法 | 入参要点 | 返回要点 |
|---|---|---|
| `save` | `company`（必填）+ `type: "need"` + 其余业务字段 | `action: created / merged / unchanged` + `id` + `company` + `creator` |
| `saveMany` | `companies` 数组，**1–100 条/次** | `total` / `created` / `merged` / `unchanged` / `failed[]` |
| `detail` | `company`（企业名精确匹配）或 `id` | 单条完整记录（含 `type` / `creator` / `status` / `heat`）；查不到返 `errCode: -1` |
| `search` | `mine: true` · `keyword` · `orderBy`（`update_time` 默认 / `create_time` / `quality_score` / `company` / `heat`）· `order`（`asc` / `desc`，默认 `desc`）· `page` · `pageSize`（默认 20，上限 50） | `list` + `total` + `text`（文本行里 `need` 会显式标「需求」，有火力值时标「火力N」） |
| `update` | `id`（必填）+ 待改字段 | `action: updated / unchanged` |
| `delete` | `id`（必填） | `deleted` + `company` |
| `stats` | 可选筛选 | `total` + 状态 / 优先级 / 行业分布 |

要点：

- **合并语义**：按企业名精确匹配，命中即合并 —— `contact` / `email` 取并集、空值不覆盖已有值；未命中则新增。
- **一家企业只挂一条需求**：去重主键就是企业名。同名再发会合并到既有那条（详情被新内容替换），**不会多出一条**。
- **`type` 只在显式传入时改写**：所以本技能传 `need` 时，如果撞上一条既有的 `lead`，那条会被**改成需求** —— 归属不变、仍是原主的。这就是必须做同名预检的原因。
- **`search` 不支持按 `type` 筛选**（服务端刻意不筛：历史行没有该字段，一筛就把存量整批静默漏掉）。要区分类型，读返回记录的 `type` —— 缺字段一律按 `lead` 处理；也可以用 `text` 里的「需求」标记快速看。
- **归属测试**：判断一条记录是不是你的 —— `search {"mine": true, "keyword": "<企业名>"}` 能捞到就是你的。
- `update` 语义是「非空即写」，传空字符串等于不改。**先核对 `creator` 是你自己再改。**
- 云对象**不做归属校验**（update / delete 只认 `id`），靠调用方自律：不是你的记录不要动。
- **`heat`（火力值）是「谁排前面」的唯一依据，且只有用户能改**：别人搜到你的需求、你和别人的需求谁靠前，看的就是它。SKILL 侧**写不进去**（服务端刻意不把这个字段放进可写白名单，否则 Agent 能绕开付费把一条需求顶到榜一）。用户想让自己那条更靠前，指引他去控制台点行尾的火力徽标投放 —— 那要扣他账号上的火力。
- **`orderBy` 传了不在白名单里的值不报错**：服务端**静默回落**成 `update_time`。要看「需求榜」用 `orderBy: "heat"` + `order: "desc"`。

## 四、同名预检（N3 必做）

写入前调一次 `detail`（`company` = 企业名），按下表分流：

| 预检结果 | 处置 |
|---|---|
| `errCode: -1`（未找到） | 直接 `save` |
| 命中，且 `type === "need"` | 告知用户「会改写既有那条需求的详情、联系方式取并集，不新增一条」，确认后再 `save` |
| 命中，且 `type === "lead"` 或缺字段 | **停下问用户**：继续会把这条改成「需求」且归属不变。用户选 继续 / 换主体名 / 放弃 |
| `errCode: -2` | 服务端异常：重试 2 次（间隔 1 秒），仍失败按「服务不可用」处理 |

## 五、错误码与处置

| errCode | 含义 | 处置 |
|---|---|---|
| `0` | 成功 | 正常，读 `action` 回报 |
| `403` | 密钥无效或缺失 | **不重试**，提示去 https://fore.vip/web/key 取 Key；本次改出需求卡片 |
| `-1` | 入参问题（缺 `company`、超长度、`type` 不在枚举内等） | 修正入参重试一次，仍失败如实回报 |
| `-2` | 服务端异常 | 重试 2 次（间隔 1 秒），仍失败改出需求卡片 |

**连通性判定**：HTTP 200 不等于成功 —— 响应体里出现「install」「not found」之类提示而非上面的结果结构，说明请求没落到服务上，按「服务不可用」处理。

## 六、鉴权：open-key

- **凭证**：用户的 open_key，在 **https://fore.vip/web/key**（「Open Key 管理」，需登录）生成。
- **传递**：HTTP 头 `X-API-Key: <open_key>`（小写 `x-api-key` 同样有效）；MCP 通道由客户端 `headers` 携带。
- **没有 Key 时**：不要臆造、不要反复重试 —— 出需求卡片并提示去上面生成。
- **Key 决定归属**：服务端用 Key 反查 uid 写 `creator`，所以**别用别人的 Key 发自己的需求**。

## 七、调用示例

```bash
# 发布一条需求（type 必须显式写 need）
curl -s -X POST https://mcp.fore.vip/crm/save \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"company":"杭州示例包装有限公司","type":"need","industry":"包装印刷","product":"瓦楞纸箱生产","contact":"0571-8888xxxx","email":"buyer@example.com","remark":"[需求] 采购食品级铝箔；首批 5 吨，月用 20 吨；含税含运月结 30 天；2026-11-30 前有效","source":"用户自述·2026-10-06"}'

# 同名预检
curl -s -X POST https://mcp.fore.vip/crm/detail \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"company":"杭州示例包装有限公司"}'

# 查我发布的需求（返回后按 type === "need" 过滤）
curl -s -X POST https://mcp.fore.vip/crm/search \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"mine":true,"pageSize":50}'

# 改我发的需求
curl -s -X POST https://mcp.fore.vip/crm/update \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"id":"<记录 id>","remark":"[需求] 采购食品级铝箔（数量已调整）"}'

# 撤下
curl -s -X POST https://mcp.fore.vip/crm/delete \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"id":"<记录 id>"}'
```

## 八、使用纪律

- **密钥不外泄**：只放请求头；不写进文件、日志、回报。确需展示只保留首末各 4 位。
- **一次只写该写的**：`type` 传 `need`，`status` / `priority` / `creator` 不传。
- **写入克制**：不批量改状态与优先级；删除只针对用户明确指定的记录；不主动清空库。
- **不代读他人数据**：读库一律带 `mine: true`。
  - ⚠️ **通道差异**：控制台（前端 clientDB，走 schema 拦截器）对非联盟会员遮蔽他人归集的 `contact` / `email` / `source`；而 **REST / MCP 这条服务端通道不经过拦截器**。所以服务端能拿到，不代表可以替用户扒出来 —— 本技能不做这件事。
- **别抢自动任务的活**：`report_url` / `quality_score` / `report_time` 由 GEO 评测自动任务回写。
