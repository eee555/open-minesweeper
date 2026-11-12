# PB 衍生榜维护文档

文件名沿用 `PB_DERIVED_PLAN.md` 以保留既有链接。原开发计划已经落地，本文改为维护文档：只记录现状口径、代码位置、变更流程、已知偏差与验证方式，不再保留计划状态、实施顺序或某次执行的结果。实现速查见 [pb_derived/README.md](pb_derived/README.md)，app 级衔接见 [竞速排行榜 README](README.md)，前端页面职责见 [RankingView README](../../../front_end/src/views/RankingView/README.md) 与 [UserView README](../../../front_end/src/views/UserView/README.md)。

## 1. 范围与代码地图

收集（Collection）、战力（Skill）、典型时（Typical Time / TT）三个逻辑大榜，共 `24 + 54 + 54 = 132` 个独立小榜，普通/NF 各一套。入口为 `/ranking/speed/collection` 与 `/ranking/speed/skill_tt`，个人 PB tab 扩展汇总展示。原 PB 榜与 LSF 默认入口不变。

事实来源链为 `VideoModel` → 原 PB service 的选优与补位 → `speedranking.pb_derived`（只用 PB 数值与固定频率表）。衍生模块不扫描录像表、不新增数据库模型、不缓存录像明细；PB 失效后的候选补位仍由原 PB service 负责。

| 位置 | 职责 |
| --- | --- |
| `pb_derived/utils.py` | 分段边界、归一化概率、132 个 field、`apply_record_delta()` 与全量 `compute()`、`defaults()`；导入期强校验，不访问数据库或 Redis，不引入同目录其他模块 |
| `pb_derived/cache.py` | `PBDerivedCache`：3 个成绩 hash、132 个小榜 zset、批量读写与区间查询 |
| `pb_derived/services.py` | 直接差量更新、全量重算回退、单项强制修复、用户删除清理、个人汇总、整榜重建 |
| `pb_derived/api.py` | Ninja 只读查询与管理员单项修复 |
| `pb_derived/signals.py` | `UserProfile.post_delete` 提交后清理 |
| `speedranking/services.py`、`pb/services.py`、`apps.py` | 共享读写 pipeline 接入、单桶修复后的重算、信号注册 |
| `management/commands/rebuild_pb_derived_ranks.py` | 全量重建命令 |
| 前端 `services/pbDerivedService.ts` | 类型、API 请求、默认排序、格式化，以及静态分段边界 `derivedSegments` 与排序键 `derivedSkillTTSortKeys` |
| 前端 `utils/derivedColors.ts` | 派生列色阶 |
| 前端 `views/RankingView/CollectionRanking.vue`、`SkillTTRanking.vue`、`PBDerivedRankingTable.vue` | 两个排行入口与共用表格 |
| 前端 `views/UserView/UserPBView.vue`、`PBSummaryStackBars.vue`、`PBRecordGrid.vue` | 个人汇总、五条堆叠条、级别标题与网格侧列 |
| `monitor/cache.py`、`dangerzone/public_snapshot.py`、`StaffView/RankingRepair.vue` | 内存监控、本地快照初始化、管理员修复入口 |

分段配置由前后端分别硬编码到代码中，不设置 version：后端 `pb_derived/utils.py:SEGMENTS` 与前端 `derivedSegments` 各存一份，原 §7「只在后端响应提供、前端不复制」的约束已推翻，两份必须同步维护（§11）。Redis 不保存配置摘要，读接口也不返回 `meta` 或版本字段；后端按边界计算成绩，前端按同一边界生成列、校验 URL 排序键并计算侧列跨度。

权限（登录、管理员/站长、本人限制）统一在 API 层：管理员写接口复用 `staff_required` 及其 CSRF 约定，读接口均为 `ratelimit(key='ip', rate='5/s')`，管理员接口不限流；service 层不重复鉴权。API 用 Ninja，文档自动生成。

## 2. 成员资格与分段

沿用原 PB 准入：STD、OFFICIAL、非隐藏比赛录像；普通 PB 包含 NF，NF PB 额外要求 `right_ce == 0`。同一 BV 在同一用户、同一等级、同一普通/NF 类别内只计一次。

按类别独立判断成员资格：至少拥有一个对应类别的 PB 才进入该类别的全部衍生小榜；只拥有普通 PB 的用户不进入 NF 衍生榜；仅缺少某级别或分段 PB 的用户仍以缺省成绩参与该类别全部小榜。最后一个对应类别的 PB 被移除时，清除该类别全部 zset member 及 hash 中的该类别字段，另一类别不受影响。用户删除时同理清理三个成绩 hash field 与 132 个 zset member。

收集 24 项：BV 数量（拥有的 PB 桶数，不是录像数）、BV 概率（所拥有 BV 的概率之和）、ASB（所拥有 PB 的 Bvs 之和），各按 `(b, i, e, sum) × (普通, NF)` 展开，均为越大越好。三项总值都直接对三级别求和；概率总值可达 3，不除以 3。

战力与典型时的分段端点均包含在内，BV 0 不属于任何区间：

| 级别 | 分段 | 段数 |
| --- | --- | --- |
| b | 1–9、10–19、20–29、30–54 | 4 |
| i | 1–39、40–49、50–59、60–69、70–79、80–89、90–99、100–216 | 8 |
| e | 1–129、130–139、140–149、150–159、160–169、170–179、180–189、190–199、200–209、210–219、220–381 | 11 |

共 23 段，每段普通/NF 各一项得 46 项；三级别合计 6 项；三级别总计 2 项，合计 54 项。战力是 PB 的 Bvs 按完整范围 BV 概率加权平均（未收集 BV 的 Bvs 按 0），越大越好；级别总战力按全级别重新计算，不能把分段战力相加；三级别总战力直接相加，不加权、不除以 3（除以 3 只用于选色）。典型时为分段平均 BV 除以分段战力，越小越好；级别总典型时是各分段典型时之和，三级别合计继续直接求和，单位为秒。

## 3. 频率数据与静态配置

[config/bv_frequencies.py](../config/bv_frequencies.py) 的 `BV_FREQUENCIES` 含 b、i、e 三个频数数组，长度分别为 55、217、382；下标即 BV，下标 0 为 0 且只作占位。缺失的前后 BV 补 0，保留原始频数，不在定义时归一化。数组直接硬编码在代码中，没有原始数据源与生成脚本，前后端各一份，变更时人工同步。

```text
f_l[v] = 等级 l 的 BV=v 的频率
Z_l = sum(f_l[v], v >= 1)
p_l[v] = f_l[v] / Z_l
```

三个等级分别归一化，不把三个数组合并后归一化；普通/NF 共用同一份概率，不从上传数据或 NF 样本重新估计。导入时一次计算概率、分段权重 `Q_I` 与平均 BV 分量 `H_I`，不在请求中反复求和。导入期强校验：有效下标上的频率有限且非负、每级总频数为正、23 个分段覆盖每个可用 BV 恰好一次且无缺口/重叠、每段 `Q_I > 0`、132 个 field 数量固定；不满足则模块无法加载。当前频率表下最小分段权重约为 i 级别 100–216 段的 `0.003643`。

分段、归一化概率、field 列表与 `ZERO_TT` 均为后端静态常量；前端的 `derivedSegments` 是另一份静态配置。两端都硬编码在代码中，不计算配置摘要、不设置 version，Redis 也没有版本 key；读接口不返回 `meta` 或任何配置元数据。因此配置变更后没有运行时信号能提示缓存已过期或前端副本已漂移，必须按 §11 同步两份并整榜重建，接口不会自动回源重算。

[front_end/src/utils/bvFrequencies.ts](../../../front_end/src/utils/bvFrequencies.ts) 是同一份频数数据的前端副本，与后端数组一起人工维护；当前页面渲染不读取该数组。分段边界另有一份前端静态配置 `derivedSegments`（§8.1），后端响应不再下发配置元数据，见 §7 与 §12.13。

## 4. 数学定义与口径锁定项

设 `S(u,m,l)` 为用户 u 在类别 m、等级 l 已拥有的 BV 集合，`I` 为一个分段或该级别完整范围，`t_v` 为 PB 的毫秒用时。计算使用数据库 Bvs 口径的未格式化原始值：

```text
bvs_v = 1000 * v / t_v if t_v > 0 else 0
S_I = S(u,m,l) ∩ I
N_I = |S_I|
P_I = sum(p_l[v], v in S_I)
A_I = sum(bvs_v, v in S_I)
W_I = sum(p_l[v] * bvs_v, v in S_I)
Q_I = sum(p_l[v], v in I)
H_I = sum(p_l[v] * v, v in I)
```

`N`、`P`、`A` 在完整等级上就是 BV 数量、BV 概率、ASB；遍历该级别全部 PB，不因权重为 0 或超出配置范围而丢弃。Bvs 不先保留三位小数再求和；显示精度与计算精度分开。

### 4.1 战力与典型时

```text
skill_I = W_I / Q_I
mean_bv_I = H_I / Q_I
tt_I = mean_bv_I / skill_I = H_I / W_I    if skill_I > 0
tt_I = 999.999                            if skill_I == 0
skill_l = sum(p_l[v] * bvs_v, v in S(u,m,l)) / sum(p_l[v], v >= 1)
tt_l = sum(tt_I, I 为该级别的所有分段)
skill_sum = skill_b + skill_i + skill_e
tt_sum = tt_b + tt_i + tt_e
```

分母固定使用完整区间概率，不按已拥有 BV 重新归一化；平均 BV 也固定取完整分段，不依赖玩家收集了哪些 BV。每级别概率已归一化，`skill_l` 分母为 1，因此级别战力可等价地由各分段战力按各段概率质量加权组合，但不能直接把分段战力相加。新增一个正权重、正 Bvs 的 BV 必然提高战力；已有 PB 提速不会降低战力；0 权重或 Bvs 为 0 的新 PB 不改变战力，不额外补权重强制增长。`999.999` 只是零战力分段的缺省值，不是上限，正战力算出的值超过它也不截断。级别总 TT 先逐段落实缺省值再直接求和，不是全级别平均 BV 除以全级别战力，也不是对分段 TT 再求平均。

现有 PB 允许 `timems == 0`；此时按 `VideoModel.bvs` 的数据库定义取 Bvs = 0，不取 Infinity、不排除该 PB，仍增加 BV 数量并按其概率增加 BV 概率。全部分段战力为 0 时，级别战力为 0，级别 TT 分别为初级 `3999.996`、中级 `7999.992`、高级 `10999.989`；三个级别都为零战力时总战力为 0、总 TT 为 `22999.977`。部分分段已有正战力时，只给其余零战力分段填缺省值。零收集值、零战力及缺省 TT 同样参与相应小榜排名；没有任何对应 PB 的用户只在个人页显示缺省值，排名为空，不因缺省展示自动入榜。

### 4.2 口径锁定项

以下为不可随意更改的口径；变更前需按 §11 整榜重建：

| 编号 | 口径 |
| --- | --- |
| D1 | 完整范围固定权重，未收集 BV 的 Bvs 为 0，不按已收集集合重新归一化。 |
| D2 | 典型时的平均 BV 按完整分段计算。 |
| D3 | 三级别总战力直接相加。 |
| D4 | 战力默认 0；零战力分段 TT 为 `999.999` 秒，缺省值逐段参与级别与总计合计。 |
| D5 | 对应类别至少拥有一个 PB 才可入榜，缺少级别或分段不额外阻止入榜。 |
| D6 | 零用时的 Bvs 按数据库口径取 0。 |
| D7 | 无频率数据的 BV 按 0 权重处理；每个配置分段总权重非零。 |
| D8 | 同分按 zset member 顺序；ASB、Skill、TT 展示三位小数，title 为精确值；BV 概率按更靠近 0 / 上限的一侧保留 3 位有效数字后还原显示。 |
| D9 | 英文命名固定为 Collection、Skill、Typical Time（TT）。 |
| D10 | Stnb 网格不追加侧列；维持各等级、所选类别首尾 PB 的显示范围。 |
| D11 | 每级别总 TT 与三级别总 TT 不上色。 |
| D12 | 3 个成绩 hash、132 个 zset、直接在成绩值上差量累加、个人排名读取时 pipeline ZRANK；double 累计误差按约定忽略。 |

## 5. 缓存结构与 field 命名

| key | 类型 | 内容 |
| --- | --- | --- |
| `speedranking:pb_derived:{ranking}:records` | hash | field 为用户 id，JSON 保存该用户此大榜的全部成绩；只保存实际入榜类别的字段，这些值本身就是差量更新的状态 |
| `speedranking:pb_derived:{ranking}:{field}` | zset | member 直接为用户 id，score 只用于排序 |

field 命名：

| ranking | field | 数量 |
| --- | --- | --- |
| `collection` | `{std\|nf}:{b\|i\|e\|sum}:{count\|probability\|asb}` | 24 |
| `skill` | `{std\|nf}:{b\|i\|e}:s{1..n}`、`{std\|nf}:{b\|i\|e}:total`、`{std\|nf}:sum:total` | 54 |
| `typical_time` | 同 `skill` | 54 |

成绩 hash 保存原始汇总值，zset 不负责还原展示数据。统一升序读取：收集、战力 score 取负值，典型时取正值；同分按 member 顺序，不设计复合 member 或拼接上传时间。展示舍入不改变 hash 或 score。所有 key 由 `PBDerivedCache.keys()` 枚举并计入监控 `pb_rankings` 分类，不依赖 `SCAN` 发现。

不额外缓存每人 rank：`/summary` 通过一次 pipeline 执行 132 项 `ZRANK`，从 0 起的结果转换为从 1 起，未入榜为 `null`。其他用户破纪录只改变 zset，不扇出刷新所有受影响用户的衍生 rank。固定 132 项的成本需要在真实规模下实测，确认成为瓶颈后再讨论 rank 缓存，不预先复制原 PB 的区间排名回写；日常更新已在成绩值上直接差量累加（§6），不额外持久化中间量、不按 PB 条数重算。

## 6. 更新链路

正常写入沿用根 `speedranking.services` 的「共同读取、独立判断、共同写入」，并采用**直接作用于成绩值的差量累加**：

1. `_read_records` 在共享读取 pipeline 中增加三次 HMGET，得到本批用户的旧成绩（132 个最终值）；`previous` 仍为五元组 `(saolei, strict_ng, pb, pb_derived, top)`，第四项为 `{player_id: {ranking: {field: value}}}`，top 快照下标为 `previous[4]`。读取命令宽度由 `PBDerivedCache.read_records()` 返回，不假设固定条数。
2. `pb_derived.prepare_changes` 对本批每个 `(player_id, field)` 变更，从旧 PB 记录取旧用时、从 PB score 还原新用时，调用 `apply_record_delta()` 直接在旧成绩上加减；同一用户在一批内只处理一次。没有额外的中间量或第二个 hash，`p_l[v]`、`Q_I`、`H_I`、`LEVEL_WEIGHTS_l` 都是导入期常量。
3. 线性部分：令 `ΔBvs = Bvs(新) - Bvs(旧)`、`ΔW = p_l[v] * ΔBvs`。收集三列分别累加 `±1`、`±p_l[v]`、`ΔBvs` 并同步累加到 `sum` 列；分段战力累加 `ΔW / Q_I`，级别总战力累加 `ΔW / LEVEL_WEIGHTS_l` 并同步累加到总计。
4. 非线性部分：分段典型时 `tt_I = H_I / W_I` 不能线性累加，由旧分段战力反推 `W_I = skill_I * Q_I`，加上 `ΔW` 后重算 `tt_I`（`W_I == 0` 取 `ZERO_TT`），再把 `Δtt_I` 累加到级别合计与总计。这正是「用分段战力算典型时，再用其变化量累加合计」。
5. `write_changes` 与原 PB 纪录同批提交：`new_values` 与旧成绩比较，只把变化的成绩 hash 与 zset 写入共享 pipeline。新类别入榜时先用 `defaults()` 初始化该类别全部字段，最后一个 PB 移除时删除该类别全部字段与 member。原 PB 自己继续刷新受影响区间的 rank 和人数。
6. 成绩缺失或与 PB 快照的类别不一致时，把 `pb_changes` 覆盖到完整 PB 映射后用 `compute()` 全量重算作为兜底；整榜重建与管理员单项修复同样以全量 `compute()` 为基准。

单个用户单次变更只更新受影响的字段，成本约为 `O(变化桶数)`，不再随该用户 PB 条数 P 增长，也不重算全部 132 项；额外临时内存是该用户成绩字典的副本 `O(132)`。理论非负的列取 `max(0, value)`，类别退出时整体删除字段，不会残留幽灵 member；反复加减带来的 double 累计误差按约定忽略，不做周期性校正，整榜重建或管理员单项修复可随时把成绩拉回全量口径。只对本批用户分段处理，不一次加载所有玩家。

必须覆盖的路径：新增、改善、变差、删除 PB，以及 player/level/BV/NF/审核或隐藏资格变化后的旧桶与新桶；标识绑定/解绑、比赛公开等批量变更时每个用户在一批内只处理一次；PB 录像 id 或上传分钟改变但 BV、用时未变时成绩不变，不刷新索引；其他玩家的 PB 排名变化不触发本用户重算。

- 单桶修复：`pb.services.rebuild_player_record` 用临时空 `previous={}` 写单桶，衍生重算不能复用该 changes。修复后由 `pb_derived.services.rebuild_player` 重新读取该用户完整 PB hash 全量 `compute()`，并 `force=True` 强制重写全部衍生索引，可补回丢失的 zset member；管理员单项修复同理。
- 用户删除：`signals.py` 的 `UserProfile.post_delete` 在 `on_commit` 后清理三个成绩 hash field 与 132 个 zset member；原 PB 缓存尚无同类清理，属于既有缺口。
- 不新增 `VideoModel` receiver 重复处理同一录像，不在 `refresh_ranks` 回写其他用户 rank 时递归触发衍生重算；新闻快照、top 锚点、管理员刷新人数同样不产生新的 PB changes。

写入沿用 `on_commit` 边界、`log_update_errors` 上下文日志、事务 pipeline 与异常传播；不引入 WATCH、全局锁、后台任务、自动重试或双写切换。并发更新同一用户仍可能覆盖，管理员单项修复与整榜重建是恢复路径。

## 7. 查询、修复与重建

| 接口 | 参数 | 行为 |
| --- | --- | --- |
| `GET /api/speedranking/pb_derived/rank` | `ranking`、`field`、`start`、`end` | 由一个小榜 zset 取人数与用户区间，同一 pipeline 读取该页成绩 hash（收集页 1 个、战力/典型时页 2 个）；左闭右开、最多 100 条；非法 field 返回 422 |
| `GET /api/speedranking/pb_derived/summary` | `player_id` | 一次返回原 PB、三个衍生大榜全部成绩与 132 项排名 |
| `POST /api/speedranking/pb_derived/admin/rebuild_player` | 表单 `player_id` | `staff_required` + CSRF，从完整 PB hash 全量重算并强制重写该用户全部衍生索引 |

两个读接口只返回成绩与排名，不携带 `meta`、version、静态分段边界、field 列表或 `zero_tt`：边界由前后端各自硬编码，前端改用 `services/pbDerivedService.ts` 的 `derivedSegments` 静态副本。这是 §7 原「单一事实来源」约束的推翻：边界在前后端各存一份，按静态配置处理，同步要求见 §11。空分页时不发起 HMGET（空 field 列表会被 Redis 拒绝），返回空 `records` 映射，不回源、不重建。缓存未命中的读接口只补缺省展示值并把该类别全部排名置空，从不自动扫描数据库或重建。

管理员「排行纪录重建」页面的 `PB 衍生榜` 选项调用单项修复。整榜重建：

```powershell
# 在 back_end/saolei 目录
python manage.py rebuild_pb_ranks          # 末尾统一调用一次 rebuild_all，保证「先 PB、后衍生」
python manage.py rebuild_pb_derived_ranks --batch-size 100  # 仅频率表/分段变更、PB 本身正确时
```

`rebuild_all` 清空命名空间后只遍历 `speedranking:pb:player:*` 重算，不查录像表；`dangerzone` 本地快照初始化因 `rebuild_pb_ranks` 的挂载点自动覆盖。执行前暂停录像上传、审核、绑定/解绑、删除、比赛公开等 PB 写入及相关读取；失败由 `log_update_errors` 记录上下文与堆栈后中断，缓存可能只完成一部分，排除错误后必须重跑。若 PB 本身有误，先重建 PB，再重建衍生数据。只读接口不自动重建。

## 8. 前端排行榜

大榜选择器顺序为 LSF、top、扫雷网、强无猜、PB、收集、战力/典型时，复用 `SpeedRanking.vue` 的提示、颜色与刷新按钮；子页通过 `defineExpose` 暴露 `refresh/loading`，接收 `colored`。URL 参数见 [排行榜 URL](../../../front_end/src/views/RankingView/README.md)：例如 `/#/ranking/speed/collection?sort=collection:sum:probability&nf=1` 与 `/#/ranking/speed/skill_tt?view=tt_e&sort=typical_time:e:s3&nf=1`。`useRankingQuery` 把子页、NF、排序、分页写入 URL，切换配置时回到第一页；`AbortController` 与请求序号保证过期响应不覆盖当前页面。

- 收集页：NF 开关；12 个成绩列依次为三级别和总计的 BV 数量、BV 概率、ASB；默认按总 BV 数量降序。排序键集合 `derivedCollectionKeys` 是静态常量，解析 URL 时即可用 `queryChoice` 校验。
- 战力/典型时页：单选子页为概览、初/中/高级战力、初/中/高级典型时，另有 NF 开关，默认进入概览。概览八列依次为三级别与总战力、三级别与总典型时，默认按总战力降序；级别子页按 BV 区间从小到大显示该级别所有分段，末列为该级别总成绩，战力按总战力降序、典型时按总 TT 升序。列头切换的是后端排序小榜，不在前端只对当前页排序。
- 两页都使用 `BaseTable` 展示，独立维护 `ElPagination`，保留排名列与 `PlayerName`；排名为 `first + index + 1`。

### 8.1 静态分段边界与排序校验

分段边界与每段 `sN` field 名由前端静态配置 `derivedSegments` 提供，与后端 `SEGMENTS` 同步维护，页面挂载时即可使用，不依赖首次响应。`derivedSkillTTSortKeys` 由同一份配置生成 54 个合法排序键，`useRankingQuery` 在解析 URL 时用 `queryChoice` 校验 `sort`，不把任意字符串交给 `/rank`（后端 `validate_field` 对非法 field 返回 422）。`effectiveSort` 只保留「排序键合法但不属于当前子页」的兜底：与当前 `columns` 比对，不匹配则回退到该子页默认排序，表格 `:sort` 与请求都使用它。因此分享链接里的 `view=tt_e&sort=typical_time:e:s3` 在第一次请求就生效，不再为取元数据多发一次请求；`selectView` 切换子页时仍把 `sort` 重置为该子页默认值。

分段子页的 `columns` 与个人页的侧列定义不再等待响应元数据；具体成绩和行仍来自接口数据，所以响应到达前表格为空态。读接口没有 `meta`，前端组件不保存或透传任何配置元数据。原「首次响应前元数据不可用」问题与本次变更的取舍见 §12.12。

## 9. 个人主页 PB

`UserPBView.vue` 只请求一次 `/summary` 并持有数据；NF 与 `time / bvs / stnb / rank` 指标切换在本地完成，不追加请求。`PBSummaryStackBars.vue` 与 `PBRecordGrid.vue` 只渲染输入。

### 顶部 stackbar

五条分别为总 BV 数量、总 BV 概率、总 ASB、总战力、总典型时，每条显示三级别构成。总值显示 `数值(排名)`，未入榜为 `--`；**三个级别分量不显示排名**，图例与提示只显示 `级别名: 占比%(数值)`。普通/NF 随现有开关整体切换，不把两类放进同一个求和。`StackBar/App.vue` 保持原有 `data/legend/tooltip/height/formatValue`，没有排名插槽；级别标志色只用于区分构成。总战力三段直接取三级别战力，总 TT 三段取各级别已包含缺省分段值的 TT。

### 级别标题与网格侧列

级别标题右侧依次追加 BV 数量、BV 概率、ASB、战力、典型时，每项显示 `数值(排名)`；ASB/战力/典型时的原生 `title` 保留未舍入原始值。标题允许换行。

| 当前网格指标 | 追加列 |
| --- | --- |
| Time | 分段典型时 |
| Bvs | 分段战力 |
| Rank | 分段战力排名、分段典型时排名两列 |
| Stnb | 不追加 |

主网格使用 CSS Grid，侧列是独立 CSS Grid，通过 `grid-row: start / span n` 让一个分段汇总 cell 跨多个十位 BV 行，无需改造整张表。初级 1–9 对应显示行 0–9，但 BV 0 仍是空位且不计入。显示范围维持所选等级及类别的首尾 PB：向十位行边界取整，范围内两端 PB 之间的空行保留，范围外不补行；没有对应 PB 时沿用空状态。跨度按分段与可见行的交集计算（`from = max(floor(start/10), firstRow)`、`to = min(floor(end/10), lastRow)`，`from > to` 直接跳过），不把区间长度当行数。如高级 1–129 在完整可见时覆盖显示行 0–9 至 120–129，实际从 BV 130 起才有 PB 时不补出前十三行；长区间只显示一个汇总 cell；显示范围内完全没有 PB 的分段按 0 战力、`999.999` 秒 TT 及相应排名渲染。分段边界来自前端静态配置，个人页不接收任何配置元数据；侧列是否渲染只取决于当前网格是否有可见行。

## 10. 数值展示与色阶

- BV 数量显示整数；ASB、Skill、TT 显示三位小数，并在数值元素的原生 `title` 中提供未按展示位数舍入的原始值。
- BV 概率显示百分比；取 `d = min(p, 上限 - p)`（单级别列上限为 1，三级别合计列上限为 3），把 `d` 保留 3 位有效数字后还原成原概率显示，所以接近上限的值不会被压成整数百分比。例如 `0.999876 → 99.9876%`（补数 0.000124）、`0.9999 → 99.99%`、`0.98765 → 98.76%`（补数 0.01235 → 0.0124）、`0.123 → 12.3%`、`0.012345 → 1.23%`、`0.00012345 → 0.0123%`、`2.999876 → 299.9876%`、`1.234 → 123%`。零显示 `0%`，恰好到上界显示 `100%` / `300%`，不显示无意义的尾随零；三级别合计不除以 3，允许超过 100%。原生 `title` 仍是未舍入的原始值。
- 排名仍为整数，不受成绩展示舍入影响；未入榜显示 `--`。格式化集中在 `front_end/src/services/pbDerivedService.ts`，两个排行页、级别标题、网格侧列与 stackbar 共用一套规则。
- 分段与级别战力使用已有 Bvs 色阶；总战力按「总战力 / 3」选色，不改变显示数值或排序值。分段典型时按秒使用对应级别 Time 色阶；级别合计、三级别合计典型时与收集三类指标不上色；stackbar 的级别标志色只表示构成。沿用全局 `local.colored` 与用户自定义色阶，缺失值不着色。规则集中在 `pbDerivedService.ts` 与 `utils/derivedColors.ts`。
- 新增的 `derived.*` 文案位于三个全局 locale；若后续修改会影响公共 VideoAnalyzer 或离线包的共享 CSS、i18n、工具与依赖，按 [Analyzer 版本管理约束](../../../front_end/local-analyzer/VERSIONING.md) 处理。

## 11. 变更与维护作业

1. **频率表或分段变更**：改 `config/bv_frequencies.py` 的 `BV_FREQUENCIES` 并同步 [前端数组](../../../front_end/src/utils/bvFrequencies.ts)（两端数组都硬编码，没有生成脚本或校验命令，必须人工核对），或改 `pb_derived/utils.py` 的 `SEGMENTS` → **同步改前端 `services/pbDerivedService.ts` 的 `derivedSegments`（端点与 `sN` 编号）** → 暂停相关读写 → 执行 `rebuild_pb_ranks`（自动含衍生）或仅 `rebuild_pb_derived_ranks`。前后端配置都硬编码且不设置 version，没有配置摘要可自动发现差异：`pbDerivedService.test.ts` 只校验前端边界连续、编号与末端 BV，不会与后端比对，改分段必须人工核对两份，也不能依据接口响应判断缓存是否需要重建。`derivedSkillTTSortKeys` 由 `derivedSegments` 自动生成，旧 URL 中已不存在的 `sN` 会在解析期回退到默认排序。不能只更新有新 PB 的用户，不能让新旧口径的成绩混排；分段数量变化时 `FIELDS` 的 132 项强校验会拦住后端遗漏。
2. **新增或调整 field / 子页**：改 `utils.FIELDS`，同步前端 `derivedCollectionKeys`、`derivedOverviewKeys`、`derivedPages`、`derivedSegments` 及列定义；`PBDerivedCache.keys()` 自动枚举新 key，监控列表无需手工补；随后整榜重建。
3. **缓存丢失或错乱**：运行 `rebuild_pb_ranks`（末尾自动整榜重建衍生数据）；不设版本标记，配置是否一致只由维护流程保证。成绩 hash 缺失或与 PB 快照的类别不一致时，该次 PB 变更会回退全量 `compute()`，但没有 PB 变更的用户会一直保留旧成绩，因此不能靠等待自愈。单个用户异常用管理员单项修复；用户删除由信号自动清理。原 PB 缓存缺少用户删除清理是既有缺口，不在衍生模块内静默补写。
4. **部署顺序**：固定「先 PB、后衍生」；`rebuild_pb_ranks` 末尾已自动重建衍生榜，无需重复执行。上线后用真实数据量实测差量更新开销、132 项 ZRANK 成本、个人响应体大小与 Redis 内存，再决定是否需要 rank 缓存，不先引入后台调度和复杂并发协议。
5. **只读接口**：缓存未命中不自动扫描数据库或重建；响应没有版本字段可供比对，配置变更后是否重建由维护流程保证，不自动触发。

## 12. 维护注意与已知偏差

1. **计划期文档中的前端相对路径已过时**：`SpeedRanking.vue` 在 `front_end/src/views/RankingView/`，`UserPBView.vue` / `PBRecordGrid.vue` 在 `front_end/src/views/UserView/`，`StackBar` 在 `front_end/src/components/visualization/StackBar/App.vue`。按本文 §1 的代码地图定位，不要按旧计划中的链接找文件。
2. **原有前端没有统一的百分比与精确值工具**：`StackBar` 用 `toFixed(0)%`，`PBRecordGrid` 的 title 曾是格式化字符串。`formatDerivedPercent`、`formatDerivedNumber`、`formatDerivedValue`、`derivedTitle`、`formatRank`、`formatWithRank` 集中在 `pbDerivedService.ts`，不要在页面各写一套。
3. **StackBar 没有排名插槽，各分量不显示排名**：`components/visualization/StackBar/App.vue` 只提供 `data/legend/tooltip/height/formatValue`，不为衍生榜新增排名插槽，也不另造第二套堆叠图。五条 stackbar 只有总值显示 `数值(排名)`；三个级别分量在图例与提示中只显示本地化级别名、占比和数值，不显示排名。因此 `StackBar/App.vue` 保持未改动，既有调用方（top 的 LSF 堆叠条、账号关联页）行为不变；`PBSummaryStackBars.vue` 通过 `name` 传入本地化级别名，避免回退后出现未翻译的 `b/i/e`。
4. **单桶 PB 修复的 `previous={}` 陷阱确实存在**：`pb/services.py:rebuild_player_record` 用空 previous 写单桶，衍生重算不能复用该 changes；修复后由 `rebuild_player(force=True)` 完整读取该用户 PB hash 重算。
5. **现有 PB 缓存没有用户删除清理**：`userprofile` 只清理 `UserMS`。新增的 `UserProfile.post_delete` 接收器只清理衍生缓存；原 PB 缓存的同类缺口属于既有问题，不在本模块静默改动。
6. **频率表分段权重校验通过**：按当前 `config/bv_frequencies.py` 实测 23 个分段 `Q_I` 全为正（最小约 `0.003643`），导入期强校验不会误报；若更换频率数组后某段权重为 0，模块会直接加载失败，需先改分段或数据。
7. **整榜重建的挂载点**：`rebuild_pb_ranks` 服务被管理命令与 `dangerzone.initialize_local_data` 共同调用，在其末尾统一重建一次衍生榜；独立的 `rebuild_pb_derived_ranks` 供概率表变更后单独使用。不要在两个入口各加一次重建。
8. **个人页只请求一次 `/summary`**：`UserPBView.cy.ts` 的 intercept 与断言维护「一次请求、NF/指标本地切换不重取」的约束；改用新汇总接口后不要把两个子组件改成各自请求。
9. **`previous` 元组形状变化影响既有测试**：为把旧衍生成绩放进共享读取 pipeline，`previous` 仍为五元组 `(saolei, strict_ng, pb, pb_derived, top)`，第四项为 `{player_id: {ranking: {field: value}}}`；`news/tests.py` 两处直接构造该元组，需同步补一个空字典；`speedranking/services.py` 中所有 top 快照下标为 `previous[4]`。`PBDerivedCache.read_records()` 返回命令宽度供 `_read_records` 切分，不再假设固定条数。
10. **`HMGET` 不接受空 field 列表**：整榜空分页时 `get_range` 只在用户区间非空时发起第二个 pipeline，空页返回空 `records` 映射，不回源、不重建。
11. **不设版本机制**：分段配置由前后端分别硬编码到代码中，Redis 不保存配置摘要，读接口也不返回 `meta` 或版本字段。分段或频率表变更没有运行时信号提示缓存已过期，必须按 §11 同步两份配置并整榜重建；不要为检测漂移重新引入 version key 或响应元数据。
12. **「分段元数据在首次响应前不可用」已由静态边界消除**：原 §7 规定边界只由后端 `meta` 提供、前端不复制，于是页面挂载时 `meta` 为 `null`：分段列为空、URL 排序键无法在解析期校验（直接发给 `/rank` 会因 `validate_field` 返回 422）、网格侧列跨度也无法计算；当时的处理是首次请求强制用默认排序取 `meta`，再由 `effectiveSort` 恢复 URL 排序键，代价是分享链接进入会多发一次请求，个人页还要用空分段占位。现在该约束已推翻：前端保存第二份静态边界 `derivedSegments`，后端不再返回 `meta`，首屏即可生成列、校验排序键与计算跨度，首次请求直接使用 URL 排序键；`effectiveSort` 只保留「排序键不属于当前子页」的兜底。维护代价从「等待响应」变为「双份配置同步」：后端 `SEGMENTS` 决定成绩，前端副本决定列、排序键与侧列，任何分段调整必须同时改两处并整榜重建（§11）；没有版本摘要，前端漂移不会被自动发现，`pbDerivedService.test.ts` 只校验前端自身连续性。旧 URL 中的过期 `sN` 由解析期 `queryChoice` 回退到默认排序。
13. **前端频率数组不参与页面渲染**：`front_end/src/utils/bvFrequencies.ts` 保留与后端相同的静态数组，供后续需要本地概率的功能使用；页面的分段边界来自 `pbDerivedService.ts` 的静态副本，不是频率数组。频率表变更需同时改两端数组（必要时连同 `pb_derived/utils.py`）并整榜重建；分段变更还需同步 `derivedSegments`（§11）。
14. **Cypress 端口约定**：组件测试默认使用 8080 端口；若端口被占用说明用户正在人工验收，应跳过测试运行，只维护 spec。E2E 测试由用户运行。

## 13. 验证

```powershell
# 在 back_end/saolei 目录
python -m flake8
python manage.py test speedranking.pb_derived --keepdb --noinput
python manage.py test speedranking news monitor common.tests.VideoUploadRankingIntegrationTest identifier tournament --keepdb --noinput

# 在 front_end 目录
npm run typecheck
npm run lint
npm run vitest -- run
npx cypress run --component --browser chrome --headless --spec "src/views/RankingView/CollectionRanking.cy.ts,src/views/RankingView/SkillTTRanking.cy.ts,src/views/RankingView/SpeedRanking.cy.ts,src/views/UserView/UserPBView.cy.ts,src/views/UserView/PBRecordGrid.cy.ts"
```

覆盖点：后端 `pb_derived/tests.py` 覆盖 23 段无缺口/重叠与正权重、全范围归一化、零权重与零用时、零战力缺省 TT 与合计、NF 隔离、选优单调性、缓存缺失回退、多步直接差量序列与全量重算一致、用时不变不改动成绩、类别退出、同分 member 顺序、用户删除、响应不含 `meta`、管理员单项修复与整榜重建；`pbDerivedService.test.ts` 覆盖格式化、排序键与默认排序，以及静态分段边界的连续、`sN` 编号与末端 BV；Cypress 覆盖请求参数、首次请求即按分享链接排序、排序、NF、分页、分段列与跨行跨度、长区间不新增行、一次请求与本地切换、级别标题数值与排名。`StackBar/App.cy.ts` 仍覆盖原有 tooltip 文本，衍生榜不重复测试组件内部实现。分段边界的**前后端一致性没有自动断言**，改分段时按 §11 人工核对并整榜重建。

后端全量 `python manage.py test` 中 `accountlink` 存在与本模块无关的超时/连接关闭时序断言，判断衍生榜回归应使用上面限定的范围，不把全量结果当作本模块的通过依据。上线后的性能实测、浏览器与深浅主题验收不能由静态检查替代。
