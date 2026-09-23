# 线索暂存服务 · 调用速查

供 SKILL.md 的 F0（前置确认）、F4（写入暂存）、F5（状态回写）使用。**只写调用方需要知道的事**：发什么、拿什么、出错怎么办。

**服务定位**：`https://mcp.fore.vip/crm` —— 只是给线索找地方**临时存放**，方便换个会话继续用。它不是长期存储：**请自行定期导出留存**，服务端不承诺永久保留。因此跑采集**前不查库**，`search` / `stats` 只在你明确要「查已有线索 / 改某家状态」时才调；重复由服务按企业名称自动合并。

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
| `status` | — | 枚举 | `未接触`（默认）/ `已触达` / `待跟进` / `已成交` / `已放弃` |
| `owner` | — | 128 | 负责人，多值半角 `;`；查不到写「待查」 |
| `remark` | — | 500 | 备注；匹配度写前缀 `[匹配度·高] …` |
| `source` | — | 256 | 来源·时间；模型知识标「模型知识·待验证」 |

- 多值字段一律半角 `;` 分隔（全角 `；` 也能被识别，但优先传半角）。
- `_id` / 时间戳由服务自管，不可写入。

## 三、各方法入参与返回

| 方法 | 入参要点 | 返回要点 |
|---|---|---|
| `save` | `company`（必填）+ 其余字段 | `action: created / merged / unchanged` + `id` |
| `saveMany` | `companies` 数组，**1–100 条/次** | `total` / `created` / `merged` / `unchanged` / `failed[]` |
| `search` | `keyword`（名称/产品模糊）· `industry` · `status` · `page` · `pageSize`（默认 20，上限 50） | `list` + `total` |
| `detail` | `id` 或 `company`（`id` 优先） | 单条记录 |
| `update` | `id`（必填）+ 待改字段 | `action: updated / unchanged` |
| `delete` | `id`（必填） | `deleted` + `company` |
| `stats` | `industry`（可选，省略即全量） | `total` + 状态分布 + 行业分布 |

要点：

- **合并语义**（写入侧唯一需要理解的规则）：按企业名称精确匹配，命中即合并——联系方式/邮箱取并集，空值不覆盖已有值；未命中则新增。**所以不用先查再写。**
- `saveMany` 单条失败不中断整批，看 `failed[]` 明细逐条回报即可，不整批回滚。
- `status` 只在**显式传入**时改写：批量写入时不要顺手传状态，避免把已跟进的打回「未接触」；改状态走单独的 `update`。
- `update` 语义是「非空即写」，传空字符串等于不改。

## 四、错误码与处置

| errCode | 含义 | 处置 |
|---|---|---|
| `0` | 成功 | 正常 |
| `403` | 密钥无效或缺失 | **不重试**，提示用户去 https://fore.vip/web/key 取 Key；本次降级本地 CSV |
| `-1` | 入参问题（缺必填、超长度、状态值不在枚举内、条数超限等） | 修正入参重试一次，仍失败降级 CSV |
| `-2` | 服务端异常 | 重试 2 次（间隔 1 秒），仍失败降级 CSV |

**连通性判定**：HTTP 200 不等于成功——响应体里若出现「install」「not found」之类的提示而非上面的结果结构，说明这次请求没落到服务上，按「服务不可用」处理（重试一次，仍不行就降级 CSV）。

## 五、鉴权：open-key

- **凭证**：用户的 open_key，在 **https://fore.vip/web/key**（「Open Key 管理」，需登录）生成，页面给出的 Key 值即凭证。
- **传递**：HTTP 头 `X-API-Key: <open_key>`（小写 `x-api-key` 同样有效）；MCP 通道由客户端配置的 `headers` 携带。
- **没有 Key 时**：不要臆造、不要反复重试 —— 直接按「服务不可用」降级本地 CSV，并提示用户去上面页面生成。
- **免鉴权**：连通性确认接口与 MCP 握手（`initialize` / `tools/list` / `ping`）。

## 六、调用示例

```bash
# 批量写入
curl -s -X POST https://mcp.fore.vip/crm/saveMany \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"companies":[{"company":"示例科技有限公司","industry":"包装印刷","contact":"0571-8888xxxx","email":"sales@example.com","owner":"待查","source":"1688·2026-09-23","remark":"[匹配度·高] 有自建厂，年采购量大"}]}'

# 状态回写（跟进后）
curl -s -X POST https://mcp.fore.vip/crm/update \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <open_key>' \
  -d '{"id":"<线索 id>","status":"已触达"}'
```

## 七、使用纪律

- **密钥不外泄**：只放在请求头里；不写进文件、日志、清单或给用户的回报中。确需展示时只保留首末各 4 位，其余打码。
- **只存企业公开信息**：官网/公开平台公示的电话、邮箱、工商信息；不存个人隐私数据。
- **克制写操作**：不批量改状态；删除只针对用户明确指定的记录；不主动清空库。
- **数据自己留底**：服务是临时存放，重要线索请自行导出。
