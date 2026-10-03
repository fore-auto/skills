# 线索暂存服务 · 调用速查

供 SKILL.md 的 F0（前置确认）、F4（写入暂存）、F5（状态回写）使用。**只写调用方需要知道的事**：发什么、拿什么、出错怎么办。

**服务定位**：`https://mcp.fore.vip/crm` —— 只是给线索找地方**临时存放**，方便换个会话继续用。它不是长期存储：**请自行定期导出留存**，服务端不承诺永久保留。因此跑采集**前不查库**，`search` / `stats` 只在你明确要「查已有线索 / 改某家状态」时才调；重复由服务按企业名称自动合并。

> **2026-09-30 起的新语义**：线索写入时会自动**归属**到 `X-API-Key` 所属用户（字段 `creator`），并支持 `priority`（高/中/低）。代理在 fore.vip 的「客户控制台」（https://fore.vip/web/crm）只能看到归属自己的线索；优先级为「高」的线索会被自动任务排入 GEO 评测队列，评测报告 URL 与质量评分由任务回写进来。**这两项都不需要 SKILL 传参**，正常批量写入即可。

## 一、端点

| 用途 | REST | MCP 工具名 |
|---|---|---|
| 单条新增/合并 | `POST /crm/save` | `save_company` |
| 批量新增/合并（主通道） | `POST /crm/saveMany` | `save_companies` |
| 检索 | `POST /crm/search` | `search_companies` |
| 详情 | `POST /crm/detail` | `get_company` |
| 更新（含状态回写） | `POST /crm/update` | `update_company` |
| 删除 | `POST /crm/delete` | `delete_company` |
| 统计 | `POST /crm/stats` | `company_stats` |
| 连通性确认 | `POST /crm/tools` | `tools/list` |

**通道按序取用**：① 运行环境已配置 crm MCP 服务 → 直接调 MCP 工具；② 否则用 HTTP 请求工具 POST 上表端点（`Content-Type: application/json`）；③ 服务不可用 → 落本地 CSV。

## 二、字段与约束

| 字段 | 必填 | 上限 | 说明 |
|---|---|---|---|
| `company` | ✅ | 128 | 企业名称（工商全称优先）。**去重主键，精确匹配** |
| `industry` | — | 64 | 行业名称 |
| `contact` | — | 256 | 联系方式，多值半角 `;` |
| `email` | — | 256 | 邮箱，多值半角 `;` |
| `product` | — | 128 | **对方企业自身**的品牌/主营产品 |
| `status` | — | 枚举 | `未接触`（默认）/ `已触达` / `待跟进` / `已成交` / `交付中` / `已完成` / `已放弃` |
| `owner` | — | 128 | 负责人，多值半角 `;`；查不到写「待查」 |
| `remark` | — | 500 | 备注；匹配度写前缀 `[匹配度·高] …` |
| `source` | — | 256 | 来源·时间；模型知识标「模型知识·待验证」 |
| `creator` | — | 64 | **归属代理 uid。一般不要传** —— 服务端按 `X-API-Key` 自动写入；只在管理员代录、需要指定归属时才显式传。**已有归属不会被覆盖** |
| `priority` | — | 枚举 | `高` / `中`（默认）/ `低`。`高` = 排入 GEO 评测队列。**改优先级走 `update`，不要在批量写入时顺手传** |
| `quality_score` | — | 0–100 整数 | GEO 质量评分，由自动任务回写；人工可覆盖。**传 `0` 是合法分**（区别于「没传」） |
| `report_url` | — | 512 | GEO 评测报告公开 URL，由自动任务回写；**非空即视为已出报告**，任务不会重复生成 |
| `report_time` | — | 毫秒时间戳 | 报告生成时间。写 `report_url` 时若不传，服务端自动补当前时间 |

- 多值字段一律半角 `;` 分隔（全角 `；` 也能被识别，但优先传半角）。
- `_id` / 时间戳由服务自管，不可写入；`creator` 一旦写入不可通过 `update` 改写。

## 三、各方法入参与返回

| 方法 | 入参要点 | 返回要点 |
|---|---|---|
| `save` | `company`（必填）+ 其余字段 | `action: created / merged / unchanged` + `id` + `creator` + `priority` |
| `saveMany` | `companies` 数组，**1–100 条/次** | `total` / `created` / `merged` / `unchanged` / `failed[]` |
| `search` | `keyword`（名称/产品模糊）· `industry` · `status` · `priority` · `mine` · `creator` · `page` · `pageSize`（默认 20，上限 50） | `list` + `total` |
| `detail` | `id` 或 `company`（`id` 优先） | 单条记录（含 `creator` / `priority` / `quality_score` / `report_url`） |
| `update` | `id`（必填）+ 待改字段（含 `priority` / `quality_score` / `report_url`） | `action: updated / unchanged` |
| `delete` | `id`（必填） | `deleted` + `company` |
| `stats` | `industry`（可选）· `creator`（可选）；均省略即全量 | `total` + 状态分布 + **优先级分布** + 行业分布 |

要点：

- **合并语义**（写入侧只需理解这一条规则）：按企业名称精确匹配，命中即合并——联系方式/邮箱取并集，空值不覆盖已有值；未命中则新增。**所以不用先查再写。**
- **归属自动落库**：写入时服务端从 `X-API-Key` 反查用户 uid 写入 `creator`；已存在的记录**归属不会被后来的写入改掉**（防串户）。所以「谁用哪把 Key 采，就归到谁名下」，SKILL 侧无需关心。
- `saveMany` 单条失败不中断整批，看 `failed[]` 明细逐条回报即可，不整批回滚。
- `status` / `priority` 只在**显式传入**时改写：批量写入时不要顺手传，避免把已跟进的打回「未接触」、把人工设的「高」冲掉；改这两项走单独的 `update`。
- `update` 语义是「非空即写」，传空字符串等于不改；`quality_score` 例外——传 `0` 会照写。
- 想只看某人的线索：`mine: true`（等价于 `creator` = 当前 Key 的 uid），或显式传 `creator: "<uid>"`。

## 四、错误码与处置

| errCode | 含义 | 处置 |
|---|---|---|
| `0` | 成功 | 正常 |
| `403` | 密钥无效或缺失 | **不重试**，提示用户去 https://fore.vip/web/key 取 Key；本次降级本地 CSV |
| `-1` | 入参问题（缺必填、超长度、状态/优先级值不在枚举内、评分超 0–100、条数超限等） | 修正入参重试一次，仍失败降级 CSV |
| `-2` | 服务端异常 | 重试 2 次（间隔 1 秒），仍失败降级 CSV |

**连通性判定**：HTTP 200 不等于成功——响应体里若出现「install」「not found」之类的提示而非上面的结果结构，说明这次请求没落到服务上，按「服务不可用」处理（重试一次，仍不行就降级 CSV）。

## 五、鉴权：open-key

- **凭证**：用户的 open_key，在 **https://fore.vip/web/key**（「Open Key 管理」，需登录）生成，页面给出的 Key 值即凭证。
- **传递**：HTTP 头 `X-API-Key: <open_key>`（小写 `x-api-key` 同样有效）；MCP 通道由客户端配置的 `headers` 携带。
- **没有 Key 时**：不要臆造、不要反复重试 —— 直接按「服务不可用」降级本地 CSV，并提示用户去上面页面生成。
- **免鉴权**：连通性确认接口与 MCP 握手（`initialize` / `tools/list` / `ping`）。
- **Key 决定归属**：服务端用 Key 反查 uid 作为线索 `creator`，所以**不要用别人的 Key 采自己的客户**。

## 六、调用示例

```bash
# 批量写入（归属与优先级都不用传：归属自动落，优先级默认「中」）
curl -s -X POST https://mcp.fore.vip/crm/saveMany \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"companies":[{"company":"示例科技有限公司","industry":"包装印刷","contact":"0571-8888xxxx","email":"sales@example.com","owner":"待查","source":"1688·2026-09-23","remark":"[匹配度·高] 有自建厂，年采购量大"}]}'

# F5 状态回写（跟进后）
curl -s -X POST https://mcp.fore.vip/crm/update \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"id":"<线索 id>","status":"已触达"}'

# 只看自己的线索（代理场景）
curl -s -X POST https://mcp.fore.vip/crm/search \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"mine":true,"pageSize":50}'
```

## 七、使用纪律

- **密钥不外泄**：只放在请求头里；不写进文件、日志、清单或给用户的回报中。确需展示时只保留首末各 4 位，其余打码。
- **只存企业公开信息**：官网/公开平台公示的电话、邮箱、工商信息；不存个人隐私数据。
- **克制写操作**：不批量改状态、不批量改优先级；删除只针对用户明确指定的记录；不主动清空库。
- **别抢自动任务的活**：`report_url` / `quality_score` / `report_time` 由 GEO 评测自动任务回写，SKILL 侧不要写（人工纠错除外）。
- **数据自己留底**：服务是临时存放，重要线索请自行导出。
