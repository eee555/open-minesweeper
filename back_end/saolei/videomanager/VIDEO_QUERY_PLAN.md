# 录像检索功能维护文档

> 本文由 2026-11-10 的「录像检索页与查询接口重做计划」整理而来。前后端已统一实现、待定项台账已清空，故只描述**当前实现**与维护约束；早期签名游标分页方案、决策过程与 Q 编号台账已移除，需要追溯请查 git 历史。文件名沿用 `VIDEO_QUERY_PLAN.md`，以免破坏外部引用。
>
> 适用范围：`back_end/saolei/videomanager/` 的查询 API 与 `front_end/src/views/DatabaseView/VideoView.vue`。接口的可机读文档由 Ninja 自动生成，本文的契约章节是维护说明，不替代自动文档。

## 1. 当前状态

| 项 | 状态 |
| --- | --- |
| 待定决策 | 0（原 Q1–Q42 全部定案或作废） |
| 后端 `/api/video/query` | 已替换旧实现 |
| 前端查询接入 | 已完成 |
| 本地检查 | 全部通过（见 §7） |
| 发布前验证 | 3 项待执行（见 §8） |

旧契约（`level/mode/o/r/ps/page/bmin/bmax/nf/s[]/count`、响应 `{count, videos}`）已删除，不提供兼容层；**前后端必须同批部署**。

## 2. 数据流

```
filterTags / sortRules
  → buildFilters() / buildSorts()            （5 秒防抖）
  → GET /api/video/query?filters=<JSON>&sorts=<JSON>
  → 后端校验白名单 → SQL（最多 1000 条、6 个网站元信息字段）
  → fetchVideoInfos() 按 ID 批量补全解析字段
  → VideoAbstract[] → 前端分页 / VideoList / 列选择
```

- 一次最多返回前 1000 条，不返回总数；页码按钮由前端按实际条数生成。
- 无游标、无续查、无服务端分页、无 Redis 结果缓存；批内数据天然是同一批。
- `VideoList` 以 `:external-filtering` 关闭表头筛选菜单，`paginator` / `sortable` 保持默认 `false`（分页与排序由本页控件负责）；行点击仍调用 `preview(id)`。
- 前端在解析字段补全完成、构造完整 `VideoAbstract` 后才整表替换，不提前展示不完整数据。

## 3. API 契约

### 3.1 请求

`GET /api/video/query`，**只接受** `filters`、`sorts` 两个查询参数；任何其它参数（含全部旧参数）返回 400。

`filters` 是 JSON 数组，一个字段一个元素，区间上下限放在同一元素内：

```json
[
  {"field": "state", "in": ["c", "a"]},
  {"field": "bv", "gte": 100, "lt": 300},
  {"field": "level", "eq": "e"}
]
```

| 约束 | 规则 |
| --- | --- |
| 算子 | `eq` / `in` / `gte` / `gt` / `lte` / `lt`；`eq` 与 `in` 不能同时出现，也不能与区间算子混用；`gte` 与 `gt`（或 `lte` 与 `lt`）不能同时出现 |
| 字段唯一 | 同一字段最多出现一次 |
| 值类型 | 按字段分组校验：整数、浮点（须有限）、ISO 时间、枚举（`MS_TextChoices` 全量取值） |
| 上限 | `in` 最多 32 个值；单个值长度上限 128 字符；结果最多 1000 条 |

用 JSON 单参数承载条件，是为了让「一个字段一个 tag、区间上下限在同一 tag 内」与前端字段去重一致；若拆成重复参数，同一 tag 的上下限会变成两个同字段条件。

`sorts` 是 JSON 数组，按数组顺序生效：

```json
[{"field": "timems", "direction": "asc"}, {"field": "bv", "direction": "desc"}]
```

`direction` 只接受 `asc` / `desc`，同一字段最多出现一次。排序键列表末尾自动追加一个 `id`（统一 asc）作为 tie-breaker，保证 1000 条顺序确定。

### 3.2 响应

```json
{"videos": [{"id": 1, "upload_time": "...", "state": "c", "ongoing_tournament": false,
             "player__id": 2, "player__realname": "..."}]}
```

6 个字段固定，不含 `count`、不含解析字段。`player__realname` 必须由 `UserProfile` 的公开 getter 取得（不能 `values('player__realname')` 绕过姓名隐私）；`ongoing_tournament=False` 对所有人（含 staff）强制。NULL 按 MySQL 默认：ASC 最前、DESC 最后；`iqg` 为 NULL 时 `stnb` 同为 NULL。

### 3.3 错误与限流

| 情况 | 结果 |
| --- | --- |
| 未知 / 旧参数、非法 JSON、白名单外字段、重复字段、算子非法或冲突、值类型错、`in` 超 32、`stnb` 无单级别前置 | 400 |
| 按 `player__realname` / `player___realname` 排序 | 400（姓名不可作排序键） |
| 超过限流 | 429 |

限流为 `ratelimit(group='video-query', key='ip', rate='1/5s', block=True)`，docstring 开头用无序列表注明。`1/5s` 强制最小间隔 5 秒、不允许分钟内突发，与前端 5 秒防抖一致。不新增语句级超时或全局中间件：nginx `uwsgi_read_timeout 2` 与 uwsgi `harakiri:10` 是硬约束，任何全表 filesort 都可能直接网关超时。

## 4. 字段与索引

| 类别 | 字段 |
| --- | --- |
| 筛选（UI 分组清单全开） | 枚举 `state / software / level / mode`；整数与浮点列（不含 `iqg`）；时间 `upload_time / end_time`；派生 `stnb`；标识 `id`（`player_id` 已移除） |
| 排序（仅已索引列） | `id, level, mode, state, timems, bv, bvs, thrp` + `stnb`（映射为 `iqg`） |

后端常量集中在 `videomanager/utils.py` 的 `VIDEO_QUERY_*`；前端对应 `fieldGroups` / `sortFieldGroups` / `sortableKeys`。不新增索引、不做大表 DDL；`VideoModel.Meta.indexes` 中可作为排序依据的只有 8 个单列索引（`level/mode/bv/bvs/iqg/thrp/timems/state`）加主键，其余 4 个是复合索引或无关列，不作为本接口的单列排序依据。`iqg` 不直接开放筛选 / 排序，只作为 `stnb` 的换算目标；`iqg_idx` 仍由 `stnb` 排序使用。

**`stnb`**：不是数据库列，而是 `STNB_COEFFICIENTS[level] × iqg`（`b=36 / i=162 / e=435`，见 `videomanager/models.py`），自定义难度返回 `None`。仅当唯一的 `level` 筛选条件恰好选中一个 `b/i/e` 值时才允许筛选或排序：阈值除以系数换成 `iqg` 区间、排序键换成 `iqg`（方向不变），走 `iqg_idx`，代价约为原生已索引列的 1 倍；跨级别会退化为 `CASE level ...` 表达式并 filesort，因此明确禁止。换算为 double 运算，边界最多差一个 ULP，以换算后的 `iqg` 区间为准，不做 Python 二次复核。未满足前置条件时，前端保留选项但禁用输入并提示、跳过该条件 / 排序键，后端直接 400。

## 5. 代码落点

| 文件 | 职责 |
| --- | --- |
| `back_end/saolei/videomanager/utils.py` | `VideoQueryError`；白名单、算子、上限常量 |
| `back_end/saolei/videomanager/schema.py` | `VideoQueryItemOut`（`create_schema`）与 `VideoQueryOut` |
| `back_end/saolei/videomanager/services.py` | `query_videos()`：参数解析、类型校验、算子映射、`stnb` 换算、排序键与 `id` tie-breaker、`LIMIT 1000` |
| `back_end/saolei/videomanager/api.py` | `video_query()`：限流、未知参数拒绝、可见性、姓名 getter、400 转换；装饰器在 docstring 开头注明 |
| `front_end/src/services/videoService.ts` | `VideoQueryFilter` / `VideoQuerySort` / `fetchVideoQuery()`（含 `fetchVideoInfos` 补全） |
| `front_end/src/views/DatabaseView/VideoView.vue` | 三板块控件、条件构造、防抖、URL 同步、分页、列选择、本地化 |
| `front_end/src/store/index.ts` | `VideoListConfig.query`（列选择持久化） |
| `front_end/src/services/videoService.md` | 接口契约说明 |

权限与可见性在 API 层；`services.py` 不读取 `request.user`、不做权限判断。旧 `Paginator` 与 `view_utils.video_all_fields` 已删除。

## 6. 前端交互规则

- **请求节奏**：首次挂载立即请求一次（初始状态不算「条件变化」）；之后 `filterTags` / `sortRules` 变化启动 5 秒防抖窗口，窗口内再变化重置计时；`AbortController` 取消在途请求，revision 丢弃过期响应。`QUERY_DEBOUNCE_MS` 与后端 `1/5s` 必须同步修改。
- **URL 同步**：筛选 / 排序 tag 与分页状态序列化到 `q` 查询参数（页面状态，不是 API 参数），用 `history.replaceState` 写入；嵌入挂载（`window.top !== window`，如组件测试）不改写宿主 URL。`q` 位于 hash 之前的 search，会随后续导航留在地址栏，故 E2E 只断言 `cy.location('hash')`，不用整条 URL 的末尾锚点。
- **tag 规则**：筛选与排序各自按字段去重（字段可以不出现、最多一次，两侧互不影响）；字段下拉过滤本板块已用字段，新增 / 切换时只提供可用字段；排序下拉只列 `sortFieldGroups`。
- **输入**：枚举多选；数值与派生字段用区间（括号切换开闭、留空表示 ±∞）；`upload_time` / `end_time` 用 `datetime-local` 并转 ISO；`stnb` 联动见 §4。
- **分页与列选择**：`pageCount` 按实际结果条数计算（空结果为 1 个 `0-0` 按钮）；列选择持久化到 `VideoListConfig.query`。
- **状态与文案**：条件变化即在结果表格显示 `v-loading`（覆盖 5 秒防抖等待与请求），刷新完成后移除；文字版 loading / 失败提示在分页区。筛选 / 排序标题、排序方向与字段标签复用全局 `button.*` / `prop.*`（en / zh-cn 缺失的字段标签回退到 dev 缩写），SFC 只保留页面专有 messages，放在 `script` 块末尾。

## 7. 测试与检查

| 命令 | 说明 |
| --- | --- |
| `cd back_end/saolei; ./.venv/Scripts/python.exe -m flake8` | 后端风格（含 `DJM100` 等本地插件） |
| `cd back_end/saolei; ./.venv/Scripts/python.exe manage.py test --noinput` | 后端单测，需本地 MySQL / Redis |
| `cd front_end; npm run lint`、`npm run typecheck` | ESLint、`vue-tsc --noEmit` |
| `cd front_end; npm run vitest -- run` | Vitest 单测 |
| `cd front_end; npx cypress run --component --browser chrome --headless --spec "src/views/DatabaseView/VideoView.cy.ts"` | 组件测试，CodeBuddy 环境下可由助手直接运行 |
| `cypress/e2e/realname-privacy.cy.ts`、`cypress/e2e/load.cy.ts` | E2E 由用户运行。前者已适配新契约（请求只含 `filters` / `sorts`、响应无 `count`）、默认列不含 `player` 需先勾选该列，以及 `1/5s` 限流下重新挂载与 reload 回放首次结果；后者按 hash 与查询请求断言 `/#/video` 重定向，不用整条 URL 的末尾锚点 |

组件测试挂载必须注入 `$axios` 并调用 `cy.mockPlayerNameFallback()`（`PlayerName → PlayerBadge → UserAvatar` 依赖链）；`mountView()` 还需重置 `VideoListConfig.value.query`，并 intercept `/api/video/query` 返回 `{videos: []}`。

2026-11-10 检查基线：flake8 0 错误；后端相关单测全通过（三模块 42 个，含新增用例的 `videomanager.test_video_info` 12 个）；`lint` 0 错误（4 个既有 warnings 在 `useAnalyzerState.test.ts`）；`typecheck` 通过；Vitest 881/881；Cypress 组件测试 8/8。

## 8. 发布前检查与已知限制

- [ ] 在生产量级数据上对每个允许的排序列跑 `EXPLAIN`，确认无 filesort 且落在 2 秒网关超时内（本地造数验证亦可）。
- [ ] 查一次生产 nginx access log，确认无站外客户端直连旧 `/api/video/query`（仓库内 CORS 白名单与公开爬取指南均不含该端点，Redoc 自动文档可见不构成直连证据）。
- [ ] 由用户运行 E2E。

已知限制：排序只开放已索引列；不新增索引；1000 条硬上限、无总数、无续查；`stnb` 换算的浮点 ULP 边界；NULL 排序依赖 MySQL 默认；旧参数不兼容，前后端必须同批部署。

## 9. 关键设计决策

| 决策 | 原因 |
| --- | --- |
| 直接替换同路径，不设并行端点 | 前后端同批部署，仓库内无站外直连证据，避免长期双写 |
| 筛选全开、排序限已索引列 | UI 约 45 个字段但只有 8 个单列索引，网关超时 2 秒；全开排序会 filesort |
| 不新增索引、不做大表 DDL | 避免 DDL 窗口与写入开销，代价是排序字段范围收窄 |
| `1/5s` + 5 秒防抖 | 强制最小间隔，避免 `12/m` 的分钟内突发；前端节奏与限流一致 |
| JSON 单参数 `filters` / `sorts` | 保证一个字段一个条件、区间上下限不拆分 |
| 不做续查 / 游标 / Redis 缓存 | 批内 1000 条由前端分页，天然是同一批数据 |
| 不开放 `ne` / `isnull` / 模糊匹配 | 与多选口径一致，避免难以索引的查询 |
| `stnb` 需单级别前置 | 系数随 `level` 变化，跨级别无法等价映射到 `iqg` 单列，且自定义难度为 NULL |
| 不开放 `iqg` 直接筛选 / 排序 | 只通过 `stnb` 换算使用，避免同一底层列出现两个语义重复入口 |

## 10. 变更记录

| 日期 | 内容 |
| --- | --- |
| 2026-11-10 | 重做计划定案（Q1–Q42），替换旧签名游标分页方案；后端 `/api/video/query` 新契约、前端 `VideoView` 接入、测试与契约文档同步；本文整理为维护文档 |
| 2026-11-11 | 页面移入 `DatabaseView/`；条件变化时结果表格显示 `v-loading`；复用全局 `button.*` / `prop.*` 文案；`iqg` 不再直接开放筛选 / 排序，`stnb` 保留；E2E 适配新契约与 URL 状态 |
