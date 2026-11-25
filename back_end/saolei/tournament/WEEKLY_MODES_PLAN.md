# 竞速打卡赛模式扩展计划

状态：主体代码、配套测试和文档已实现；Cypress 验收与生产部署待执行。本文保留业务约定和实现检查清单，未完成项继续以 TODO 标记。

## 已确认的规则与范围

- 四个赛制的展示前缀分别为：**经典、NF、强无猜、强无猜NF**。经典即现有标准模式赛制。
- **每周最多一场竞速打卡赛，由管理员创建时选择一个赛制**，不是同周四场，也不是一次报名生成四套成绩。
- 除录像模式和 NF 限制外，其他规则与原标准赛完全一致，包括 2 高 5 中、60/240 秒上限、缺局补位、两小时个人窗口及积分系数 50。
- 普通赛制包含对应 NF 录像：经典包含标准 NF，强无猜包含强无猜 NF。
- 四个赛制分别维护历史总积分和 best；`weekly_total` 为四者合并总积分。比赛总榜的竞速部分只展示该合并总分，竞速打卡赛榜同时展示四组分项总积分/best 和合并总分，共九个指标列。
- 继续使用 `WeeklyTournament` / `WeeklyParticipant` 和现有 `tournament_format`，不新增 subclass、app 或另一个独立的 mode 字段。
- 不改变 GSC 和效率打卡赛的筛选、计分或积分规则。
- 竞速与效率比赛仍可独立报名，个人窗口可以重叠；本次不改变跨比赛录像标识和归属规则。

## 录像规则

采用以下筛选规则；实现拟用以下赛制编码，原有 `c` 保持不变。

| 赛制 | `tournament_format` | 后端录像条件 | 前端对应条件 |
| --- | --- | --- | --- |
| 经典 | `c` | `mode=STD ('00')` | `MS_Mode.Standard` |
| NF | `n` | `mode=STD ('00')` 且 `right_ce=0` | 标准模式且 `video.right_ce === 0` |
| 强无猜 | `q` | `mode=QWC ('06')` | `MS_Mode.HardcoreNG` |
| 强无猜NF | `f` | `mode=QWC ('06')` 且 `right_ce=0` | 强无猜模式且 `video.right_ce === 0` |

NF 沿用项目排行榜现有的有效右键判定，不能用 `right == 0` 替代。缺少 `right_ce`（数据库 NULL、前端 NaN）不视为 NF。强无猜不是竞速无猜 `JSW ('05')`，不能将两者混用。

经典赛包含标准 NF；强无猜赛包含强无猜 NF，不把普通赛定义为“必须使用有效右键”。每场只按管理员选定的一个赛制结算和发分，满足 NF 条件不会额外发放另一赛制的积分或更新另一赛制的 best。

其余条件保持现状：

- 仅 OFFICIAL 录像计分；未完成录像仍由现有上传完成性检查拒绝，不放宽标识绑定和审核规则。
- 中级用时严格小于 60000 ms，高级严格小于 240000 ms；各取最好的 5 局、2 局，按整数毫秒求和，越小越好。
- 不足局数按中级 60000、高级 240000 补位，默认总成绩为 780000 ms。
- 积分系数为 50，沿用现有 `round(weight / rank)` 发分逻辑，不增加多赛制积分叠加或额外奖励。
- 不额外增加 3BV 下限、软件白名单或新的成绩并列规则。
- 比赛录像归属与计分资格继续分离。已关联比赛但不符合本赛制条件的录像不计分，不因此删除关联；结算清理、报名重置仍按“是否有任何比赛录像”判断。

## 实施前的兼容检查

以下记录实施前的限制及本次处理方式；对应改动已完成，不能在后续调整时退回仅增加枚举的实现：

| 位置 | 实施前行为 | 本次处理 |
| --- | --- | --- |
| `WeeklyTournament.Meta`、`weekly.api.new_weekly_tournament` | 按 `(year, week)` 唯一 | 保留约束和重复检查；即使选择不同赛制，同周再次创建仍应拒绝 |
| `WeeklyTournament.order_by` | 只对 CLASSIC 返回排序字段 | 四种赛制都按 `classic_score` 排名 |
| `weekly.services._weekly_score_videos` | 只有 CLASSIC 分支限制录像模式 | 四种赛制显式筛选，不能让新赛制落入“不限制模式”的分支 |
| `weekly.services` 的 best 计算 | 所有竞速记录都进入 `weekly_classic_best`，历史查询未筛选 format | 按赛制计算、回退和重建 best |
| `services.award_tournament_rank_scores` | 非 CLASSIC 竞速赛没有赋值 `add_score_category` | 补全积分分类，避免结算失败 |
| `services.refresh_tournament_user_total_fields` | 直接令 `weekly_classic_total = weekly_total` | 按赛制分别汇总，再计算竞速总积分 |
| `signals.py` 的删除扣分、`weekly.signals` | 默认所有竞速记录属于经典赛制 | 按原比赛赛制撤销积分、重建对应 best |
| `refresh_tournament_scores` 命令 | 拒绝非 CLASSIC 竞速赛 | 允许重算全部四种赛制 |
| `front_end/src/utils/weekly.ts` | `WeeklyParticipant` 只计算标准模式，没有赛制信息 | 将比赛赛制传入实例，统一用于即时成绩计算 |
| `weekly/App.vue`、`PersonalSummary.vue` | 自动上传和个人成绩展示均有 Classic 限制 | 支持四种赛制，复用现有布局 |

## 数据模型与缓存

### 比赛和参赛者

- [x] 扩展 `config.text_choices.Tournament_TextChoices.WeeklyFormat`，前后端编码保持一致。
- [x] 保留 `(year, week)` 唯一约束和创建查询，不把 `tournament_format` 纳入唯一键。验证同周选择另一赛制也不能重复创建。
- [x] 沿用 `(tournament, user)` 报名唯一约束。选手报名当周比赛，其赛制由比赛记录决定；个人窗口仍为两小时，并被比赛 `end_time` 截断。
- [x] 保留 `WeeklyParticipant.classic_et`、`classic_it`、`classic_score` 字段名和存储结构。一条参赛记录只属于一个赛制，不为四个赛制各建一组录像数组。
- [x] 管理员仅在创建时选择赛制，不新增创建后的赛制修改入口，避免已报名的 token、成绩、积分分类及缓存含义变化。
- [x] 现有 `tournament:normal` 缓存已保存 `tournament_format`，继续复用；参赛者缓存继续按用户存多场报名，不增加单独的模式索引。

### 用户积分和最好成绩

不同赛制分别维护总积分与 best，只更新比赛所属赛制的字段，不能因录像也符合另一赛制就跨赛制累计。字段方案如下：

| 赛制 | 历史总积分 | best |
| --- | --- | --- |
| 经典 | 保留 `weekly_classic_total` | 保留 `weekly_classic_best` |
| NF | 新增 `weekly_nf_total` | 新增 `weekly_nf_best` |
| 强无猜 | 新增 `weekly_qwc_total` | 新增 `weekly_qwc_best` |
| 强无猜NF | 新增 `weekly_qwc_nf_total` | 新增 `weekly_qwc_nf_best` |

- [x] 保留 `weekly_total`，表示全部竞速赛制的历史总积分之和；`score_total`、`score_current` 继续汇总各类比赛，不修改当前积分的衰减公式和年度时间锚点。
- [x] 新总积分字段沿用零默认值；新 best 沿用 `PositiveBigIntegerField`、`MAX_TOURNAMENT_BEST` 和 `weekly_encode_best(score, year, week)`，前端解码成绩与年/周。
- [x] 同步 `TournamentUser.add_score`、发分、删除撤分、历史汇总和 best 保存/删除信号。重算按新旧 `rank_score` 差额处理，不重复发分；撤分仍考虑比赛结束时间对应的衰减系数。
- [x] best 的历史查询必须增加赛制过滤，删除参赛者后只能在同一赛制内回退；批量刷新及管理命令也按赛制分开。
- [x] 为新增六个字段扩展 `TournamentCache` 的 key、默认值、排序方向和批量更新。排行榜 zset 从 9 个增加到 15 个，member 仍为 `user_id`；best 升序，积分降序，默认值不入榜。
- [x] 同步排行榜 API 排序字段白名单、`create_schema` 输出、缓存重建命令及监控中的缓存 key 统计。沿用既有 Redis 原子更新，不为模式扩展另造缓存机制。

## 后端与任务

- [x] 在 `weekly.utils` 集中定义赛制对应的录像模式、是否要求 NF 和积分字段分类。工具模块不引入同 app 的模型；服务按此规则构造查询。
- [x] 复用一个 2 高 5 中的成绩刷新服务，按赛制筛选后仍分别查询高级和中级、批量保存。不复制四套结算算法；函数名称若一般化，同步所有调用点。
- [x] API 输入使用明确的赛制类型，未知值在创建前拒绝；服务和模型遇到未知值也不能默认为标准赛或不筛选。
- [x] 复用 `/api/tournament/weekly/new`、`/participant`、`/results`。报名只提交比赛 ID，赛制由比赛决定；普通比赛详情已经携带 format，不增加重复获取赛制的请求。
- [x] 复用现有结算任务，继续按比赛 ID 定位，最早在 `end_time + 1 小时`执行；积分和 best 后续任务继续沿用，不合并不同赛制的结算。
- [x] 保留现有单 worker 串行结算约定；人工重算命令避免和 worker 的发分、取消资格任务重叠。竞速与效率等比赛仍共享用户积分，不能以每周只有一场竞速赛替代写入一致性约束。
- [x] 同步 `refresh_tournament_scores`、`refresh_tournament_user_stats`、缓存重建及其他调用点，确保重算非标准赛不会改变标准赛的 best。
- [x] 为父类和竞速子类参赛者增加 `pre_delete` 上下文捕获，级联删除前保留完整比赛实例；实际扣分仍只在父类 `post_delete` 执行一次，best 按所属赛制重建。
- [x] 同步 dangerzone 测试工厂的赛制参数；`init_local_test.py` 等入口保留按年/周查找或创建的语义和经典默认值，不在同周另建其他竞速赛制。

## 前端

- [x] 扩展 `WeeklyTournamentFormat` 和比赛数据类型，管理员创建竞速赛时可选四个赛制，默认经典；效率赛不增加该选项，每周仍只创建一场竞速赛。
- [x] 比赛名称、描述、选项和表头统一使用“经典”“NF”“强无猜”“强无猜NF”前缀，覆盖后端名称、列表、首页 NORMAL 比赛区域、独立比赛页和创建结果。
- [x] `WeeklyParticipant` 持有明确赛制；列表加载、已颁奖结果、注册返回、个人成绩展示和自动上传均使用同一赛制。优先从父组件已取得的比赛信息传入，不额外请求。
- [x] 在 `weekly.ts` 内复用一个赛制资格判断，用于个人即时计分和周赛组件内的自动上传筛选；不修改通用 AutoUploader 的 slot/filter 设计，也不新增跨赛种的通用筛选框架。
- [x] 自动上传保留三档：匹配本场 token；再要求模式/级别符合本赛制（NF 场额外检查 `right_ce`）；再要求用时优于本人的入选末位。上传成功后仍根据后端 state 决定是否进入即时成绩，不能把本地解析状态当作 OFFICIAL。
- [x] 复用现有 AllSummary、2 高 5 中 PersonalSummary 和可视化，不为四种赛制各复制一个页面；移除仅 Classic 才渲染的限制。
- [x] 保留总榜、GSC、竞速、效率四个排行榜入口，不增加竞速榜内的赛制选择器。总榜的竞速部分只显示 `weekly_total`，不展开四个赛制；其他赛种及当前积分等既有列保持不变。
- [x] 竞速打卡赛榜同时显示下表九个指标列，另保留名次和 PlayerName。best 仍解码成绩与年/周，届号在对应 best 单元格内展示，不额外增加四个届号列；九个指标均可按表头排序，积分降序、best 升序。
- [x] 同步前端 API 类型、排序字段、分页请求及中英西文案，不改日期格式和无关表格交互。

| 指标列 | 字段 |
| --- | --- |
| 总积分 | `weekly_total` |
| 经典总积分 | `weekly_classic_total` |
| 经典最好成绩 | `weekly_classic_best` |
| NF 总积分 | `weekly_nf_total` |
| NF 最好成绩 | `weekly_nf_best` |
| 强无猜总积分 | `weekly_qwc_total` |
| 强无猜最好成绩 | `weekly_qwc_best` |
| 强无猜NF总积分 | `weekly_qwc_nf_total` |
| 强无猜NF最好成绩 | `weekly_qwc_nf_best` |

## 兼容、上线与文档

部署时暂停相关写入和 worker，在 `back_end/saolei` 执行以下命令；迁移仍由服务器自动生成：

```bash
python manage.py makemigrations tournament
python manage.py migrate
python manage.py refresh_tournament_user_stats
python manage.py rebuild_tournament_cache
python manage.py rebuild_tournament_user_cache
```

核对旧经典积分和 best 不变、新赛制默认值不入榜，再恢复 worker。无需重跑所有历史比赛结算。

- [x] 旧 `tournament_format='c'` 的比赛、报名、成绩和积分含义不变，展示前缀统一为经典；不把旧标准 NF 录像另建为历史 NF 比赛，不补发新赛制积分或 best。
- [x] 模型调整使用 Django 自动生成迁移，沿用服务器生成迁移的部署方式，不手写迁移文件。
- TODO：新增字段默认值不会自动拆分历史数据。上线时暂停相关写入和 worker，执行用户汇总/best 刷新及缓存重建，确认标准赛历史值不变后恢复。这里重建汇总不等于重跑所有历史比赛结算。
- [x] 同步中英文打卡赛指南，明确每周只有一个管理员选定赛制、普通包含 NF、只累计比赛所属赛制的积分和 best，以及四赛制前缀。保留与效率赛独立报名、窗口可重叠和多个比赛标识的既有规则；只发布已实现的内容。
- [x] 同步开发文档 `cache.md`、`signals.md`、`management-commands.md`，以及 `VIDEO_DELETION_PLAN.md` 中仅描述经典赛制的范围。

## 测试与验收

- [x] 用参数化测试覆盖四种赛制资格矩阵：STD/QWC/JSW、`right_ce` 为 0/非零/NULL、非 OFFICIAL、初级及自定义级别。NF 口径覆盖“有原始右键但有效右键为零”。
- [x] 覆盖严格时间上限、缺局补位、2 高 5 中选择、重复重算、录像状态变化和普通录像删除后的显式重算；不复制四份同结构测试。
- [x] 验证管理员可选择任一赛制创建周赛，同周第二场无论赛制是否相同都被拒绝；不同周可选不同赛制。参赛者仍只能报名当周这一场竞速赛，与效率赛的独立报名和重叠窗口保持不变。
- [x] 验证经典接收标准 NF、强无猜接收强无猜 NF，但不额外更新 NF 专属积分或 best；NF 场不更新经典专属字段。不同赛制的发分、差额重算、撤分和 best 回退互不串场，`weekly_total` 等于四个分项之和，缓存排序和默认值排除正确。
- [x] 前端 Vitest 覆盖各赛制的 `WeeklyParticipant` 计算；组件测试覆盖创建时赛制选择、个人成绩、自动上传三档及竞速榜九个指标列与排序，复用现有测试工具。
- TODO：由用户运行已扩展的真实后端 E2E 及相关 Cypress 组件测试；复用批量测试数据初始化，不等待真实两小时。

## 实施状态

1. 已实现：完成后端赛制筛选、分项积分/best、缓存及管理命令，先验证旧经典数据兼容和每周唯一约束。
2. 已实现：对接管理员赛制选择、比赛名称、即时成绩、自动上传和竞速榜九个指标列。
3. TODO：文档与测试代码已同步；由用户运行 Cypress 后，按上线步骤迁移并重建汇总缓存。
