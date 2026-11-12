# PB 衍生榜

由用户现有的 `(普通/NF, level, BV)` PB 与固定 BV 频率表计算收集、战力、典型时三个大榜。本模块不新增数据库模型、不扫描录像表，只在 `speedranking.services` 已有的一次共享读写 pipeline 中读取旧成绩，对变化的 PB 桶直接加减其贡献，不额外维护中间量。

数学口径、代码地图、变更流程与维护注意见 [`speedranking/PB_DERIVED_PLAN.md`](../PB_DERIVED_PLAN.md)，本文只保留实现速查。

## 代码组织

| 文件 | 职责 |
| --- | --- |
| `utils.py` | 分段边界、归一化概率、132 个 field 名、直接差量 `apply_record_delta()` 与全量 `compute()`；导入时校验配置 |
| `cache.py` | `PBDerivedCache`：3 个成绩 hash、132 个小榜 zset、批量读写与区间查询 |
| `services.py` | 直接差量更新、全量重算回退、单项强制修复、用户删除清理、个人汇总、整榜重建 |
| `api.py` | Ninja 只读查询与管理员单项修复 |
| `signals.py` | `UserProfile.post_delete` 的提交后清理 |
| `tests.py` | 纯计算、缓存、API、重建、删除清理测试 |

`utils.py` 不引入同目录其他模块，也不访问数据库或 Redis；`services.py` 只复用 `pb.cache` / `pb.utils` 的既有读取与 score 解码能力，不复制录像查询与补位逻辑。

## 计算口径

`config/bv_frequencies.py` 的 b/i/e 频数数组下标 0 仅占位。每级别把 `1..N` 的频数按总和归一化成 `p_l[v]`；分段端点均包含在内，BV 0 不属于任何分段，三段级别覆盖 `1..54`、`1..216`、`1..381`。分段总权重必须为正，导入时校验，否则模块无法加载。

对用户某一类别（普通或 NF）的全部 PB，`Bvs_v = 1000 * v / timems`（用时为整数毫秒，`timems == 0` 时取 0）：

- 收集：级别 BV 数量 `N_l = |PB_l|`，BV 概率 `P_l = Σ p_l[v]`，ASB `A_l = Σ Bvs_v`；`sum` 是三级别之和。频率表范围外或权重为 0 的 BV 仍计入 BV 数量与 ASB，只是权重为 0。
- 分段：`Q_I = Σ p_l[v]`、`H_I = Σ p_l[v] * v`、`W_I = Σ p_l[v] * Bvs_v`；`skill_I = W_I / Q_I`，`tt_I = H_I / W_I`（`W_I == 0` 时取 `999.999` 秒）。
- 级别总战力 `skill_l = Σ p_l[v] * Bvs_v / Σ p_l[v]` 从全级别重新计算，不把分段战力相加；级别合计典型时是各分段 `tt_I` 之和，三级别合计是三个级别合计之和。总战力是三个级别战力之和。

普通与 NF 完全分离；某类别没有任何 PB 时，该类别不写入 hash、不进入任何小榜 zset，个人接口补缺省展示值并把该类别全部排名置空。`ZERO_TT` 只进入分段/合计典型时，不进入战力与收集值。

新增一个正权重且 `Bvs > 0` 的 PB 必然提高战力；提高已有 PB 的 Bvs 必然提高战力并降低对应分段典型时。

## 分段与 field

| ranking | field | 数量 |
| --- | --- | --- |
| `collection` | `{std\|nf}:{b\|i\|e\|sum}:{count\|probability\|asb}` | 24 |
| `skill` | `{std\|nf}:{level}:s{1..n}`、`{std\|nf}:{level}:total`、`{std\|nf}:sum:total` | 54 |
| `typical_time` | 同 `skill` | 54 |

分段：b 为 `1–9 / 10–19 / 20–29 / 30–54`；i 为 `1–39 / 40–49 / … / 90–99 / 100–216`；e 为 `1–129 / 130–139 / … / 210–219 / 220–381`。共 23 个分段，加上三级别合计与三级别总计共 27 个战力/典型时小榜位置，乘普通/NF 得 54。

前端在 `front_end/src/services/pbDerivedService.ts:derivedSegments` 保存同一份静态边界，用于生成分段列、校验 URL 排序键与计算网格侧列跨度；页面挂载即可使用，不依赖 `meta`。改分段必须同步前后端两处；两端配置都硬编码且不设置 version，前端副本漂移不会被自动发现。

分段、概率、field 列表与 `ZERO_TT` 分别硬编码在前后端代码中，不计算配置摘要、不设置 version：Redis 没有版本 key，读接口也不返回 `meta`。修改频率表或分段后旧 zset score 会与新配置混排，接口不会自动扫描数据库重算，也没有运行时信号提示缓存已过期；必须同步两份配置并整榜重建，前端漂移只能人工核对或由 `pbDerivedService.test.ts` 检查前端自身连续性。

## 缓存键

| key | 类型 | 内容 |
| --- | --- | --- |
| `speedranking:pb_derived:{ranking}:records` | hash | `field = user_id`，value 为该用户此大榜全部成绩的 JSON；这 132 个值就是差量更新的状态 |
| `speedranking:pb_derived:{ranking}:{field}` | zset | `member = user_id`，score 为收集/战力取负、典型时取正，均按 `ZRANGE` 升序读取 |

同分按 member 字典序，member 直接是用户 id，因此不存在 `user_id:video_id` 的拼接歧义。所有 key 由 `PBDerivedCache.keys()` 枚举并计入监控 `pb_rankings` 分类，不依赖 `SCAN` 发现。

## 更新与修复

- 正常路径：`speedranking.services._read_records` 用三次 HMGET 加入共享读取 pipeline；`prepare_changes` 从旧成绩出发，对每个 `(player_id, field)` 变更取旧用时、从 PB score 还原新用时，调用 `apply_record_delta()` 直接加减成绩值，再由 `write_changes` 只把与旧成绩不同的 hash 与 zset 写入共享写入 pipeline，与原 PB 纪录同批提交。没有额外的中间量或第二个 hash，只更新受影响的字段，不遍历该用户的 PB 条数。三次 HMGET 中的 `skill:records` 提供旧分段战力、`typical_time:records` 提供旧分段典型时，是计算 `tt_I` 及其变化量的必要输入；`prepare_changes` 在差量前校验本批涉及的分段字段齐全，缺失则回退全量重算。`_update_videos` 的批量路径（标识绑定/解绑、比赛批量公开、批量失效补位）与单条 `sync_video` 共用这条链路，同样逐桶差量、同一用户一批只处理一次。
- 差量公式：令 `ΔBvs = Bvs(新) - Bvs(旧)`、`ΔW = p_l[v] * ΔBvs`。收集三列分别累加 `±1`、`±p_l[v]`、`ΔBvs` 并同步累加到 `sum` 列；分段战力累加 `ΔW / Q_I`，级别总战力累加 `ΔW / LEVEL_WEIGHTS_l` 并同步累加到总计；分段典型时是非线性的，由旧分段战力反推 `W_I = skill_I * Q_I`，加上 `ΔW` 后重算 `tt_I = H_I / W_I`（`W_I == 0` 取 `999.999` 秒），再把 `Δtt_I` 累加到级别合计与总计。`p_l[v]`、`Q_I`、`H_I`、`LEVEL_WEIGHTS_l` 都是导入期常量，不存 Redis、不在请求里重算。分段贡献归零时必须把 `W_I` 按相对量级精确置 0，不能把相减的浮点残差留给 `H_I / W_I`（会被放大到 1e18 量级）；此时分段典型时直接复位为 `999.999` 秒，并把 `999.999 - 旧tt_I` 作为差量累加到级别合计与总计，重新加入该 PB 时方能精确还原。
- 类别入榜/退出：新类别用 `defaults()` 初始化该类别全部字段后再累加；最后一个 PB 移除时删除该类别全部字段与 zset member，不残留幽灵值。理论非负的列取 `max(0, value)`；反复加减的 double 累计误差按约定忽略。录像 id 或上传分钟改变但 BV、用时未变时成绩不变，不刷新索引。
- 缓存缺失或不一致（新用户首次写入、成绩 hash 与 PB 快照的类别不匹配）时 `prepare_changes` 回退 `compute_for_records()`，把 `pb_changes` 覆盖到完整 PB 映射后全量重算；没有 PB 变更的用户不会自愈，因此缓存丢失仍需整榜重建或管理员单项修复，配置变更后也必须整榜重建。
- 递归风险已排除：PB 刷新 rank、新闻快照、top 锚点、管理员刷新人数都不产生新的 PB changes；模块不新增 `VideoModel` 接收器。
- `pb.services.rebuild_player_record` 用 `previous={}` 写单桶，衍生重算不复用该 changes：修复后调用 `services.rebuild_player(player_id)`，重新读取该用户完整 PB hash 用 `compute()` 全量重算并 `force=True` 重写全部衍生索引，可补回丢失的 zset member。管理员入口为 `POST /api/speedranking/pb_derived/admin/rebuild_player`（`staff_required`，表单 `player_id`）。
- 用户删除由 `signals.py` 的 `UserProfile.post_delete` 在 `on_commit` 后清理该用户三个成绩 hash field 与全部 132 个 zset member。原 PB 缓存尚无同类清理，属于既有缺口。
- 整榜重建：`python manage.py rebuild_pb_derived_ranks [--batch-size 100]`，清空命名空间后仅遍历 `speedranking:pb:player:*` 全量重算，不查录像表；`rebuild_pb_ranks` 末尾也会统一调用一次，`dangerzone` 本地快照初始化因此自动覆盖。第一版不引入双写/原子切换，执行前暂停相关读写；失败由 `log_update_errors` 记录上下文与堆栈后中断，缓存可能只完成一部分，排除错误后必须重跑。

`GET /rank?ranking=&field=&start=&end=` 由一个小榜 zset 取人数与用户区间，同一 pipeline 读取该页所需成绩 hash（收集页 1 个、战力/典型时页 2 个）；`start/end` 左闭右开，最多 100 条。非法 field 返回 422。`GET /summary?player_id=` 一次返回原 PB、三个大榜全部成绩与 132 项从 1 起的排名；缓存未命中只补缺省展示值，不重建。两者都只返回成绩与排名，不携带 `meta`、版本摘要、静态分段边界、field 列表或 `zero_tt`；前端使用 `derivedSegments`，见 [维护文档 §7](../PB_DERIVED_PLAN.md)。管理员写接口不设 ratelimit，读接口均为 `ratelimit(key='ip', rate='5/s')`。

## 展示约定

BV 数量显示整数；BV 概率取 `min(p, 上限 - p)`（单级别列上限 1、三级别合计列上限 3）保留 3 位有效数字后还原成原概率显示，例如 `0.999876 → 99.9876%`（补数 0.000124）、`0.123 → 12.3%`、`0.98765 → 98.76%`、`0.012345 → 1.23%`、`2.999876 → 299.9876%`、`1.234 → 123%`；接近上界的值不会被压成整数百分比，小概率也不会被固定小数位显示为 0，零与恰好到上界显示 `0%` / `100%` / `300%`。ASB、战力、典型时显示三位小数，原生 title 保留未舍入的原始值。未入榜类别的排名显示 `--`。

分段战力用已有 Bvs 色阶，级别战力用同一色阶的原始值，总战力按 `总战力 / 3` 选色；分段典型时按秒数使用对应级别 Time 色阶，级别合计典型时、三级别合计典型时与收集各列不着色。stackbar 的三级别标志色只表示构成，不表示强弱色阶。缺失值不着色。规则集中在 `front_end/src/services/pbDerivedService.ts`、`front_end/src/utils/derivedColors.ts`，两个排行页面、个人级别标题、网格侧列与 stackbar 共用。

## 测试

```bash
python manage.py test speedranking.pb_derived --keepdb --noinput
npx vitest run src/services/pbDerivedService.test.ts
npx cypress run --component --browser chrome --headless --spec "src/views/RankingView/CollectionRanking.cy.ts,src/views/RankingView/SkillTTRanking.cy.ts,src/views/UserView/PBRecordGrid.cy.ts,src/views/UserView/UserPBView.cy.ts"
```

后端覆盖 23 段无缺口/无重叠与正权重、全范围归一化、零权重与零用时、零战力缺省 TT、三级别合计、NF 隔离、选优单调性、缓存缺失回退、多步差量序列与全量重算结果一致、批量多用户与同一分段多桶差量、分段战力缺失回退、批量导入不回退全量、用时不变不改动成绩、类别退出、同分 member 顺序、用户删除、API、管理员单项修复与整榜重建。前端覆盖格式化、URL 排序、NF、分段列、跨行跨度、长区间不新增行、一次请求与本地切换。
