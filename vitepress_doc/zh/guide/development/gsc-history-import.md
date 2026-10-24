---
title: GSC 历史录像补录 - 开源扫雷网
description: GSC 历史录像补录的前后端流程、标识绑定、查重、上传时间处理及各 API 的职责。
---

# GSC 历史录像补录

本文描述已实现的历史补录流程，重点是有站内账号且能提供录像的情况；缺失录像时使用成绩 CSV。入口位于 `GSCAdminView` 的“历史成绩补录”。接口字段和响应 Schema 以 Ninja 自动生成的 API 文档为准。

## 业务边界

- 历史写入接口仅允许比赛的实际主办方或网站管理员操作，要求比赛为 `AWARDED` 且有 `end_time`。每次请求重新校验，不沿用准备请求的授权。读取比赛信息和成绩复用现有公开接口，不新增管理列表 API。
- 权限统一由 API 控制：API 在事务内查询并锁定比赛，校验操作者及比赛状态，再将已授权的比赛、用户或参赛者对象传给 services。services 不接收 `actor`，不重复查询权限；锁一直持有到本次写入事务结束。
- 历史补录写入接口对网站管理员和比赛主办方均不限流；这不改变权限校验、单标识绑定或每批最多 10 条成绩的限制。
- `order` 是 GSC 届数；`tournament_id` 是父表 `Tournament` 的 ID；`participant_id` 是参赛者 ID，三者不能混用。
- 代传不检查实名及录像数量限制，但仍检查完成性、标识安全与归属，不能强行把冻结或标识不匹配的录像变为 `OFFICIAL`。
- 补录接口不自动从录像重算比赛成绩、刷新排名或发放积分，也不创建后台结算任务。创建 participant 时正常执行 best 保存信号，允许用默认成绩或手工成绩改善 `gsc_best` 并同步排行缓存。标识绑定和录像保存仍触发原有录像状态、队列与排行榜维护；删除参赛者也保留撤分及 best 更新信号。

## 完整录像流程

图中蓝色节点是 API，灰色节点是前端处理，绿色节点是服务或数据写入，黄色节点是人工命令。

```dot
digraph gsc_history_flow {
    graph [layout=dot, rankdir=TB, bgcolor="transparent", nodesep=0.35, ranksep=0.65, splines=polyline];
    node [shape=box, style=filled, fillcolor="${#f1f5f9|#1f2937}", color="${#94a3b8|#64748b}", fontcolor="${#0f172a|#e5e7eb}", fontsize=12];
    edge [color="${#64748b|#94a3b8}", fontcolor="${#475569|#cbd5e1}", fontsize=10, arrowsize=0.7];

    info [label="读取比赛信息\nget_GSC_tournament", fillcolor="${#dbeafe|#1e3a5f}"];
    participants [label="读取已保存的参赛成绩\nget_results", fillcolor="${#dbeafe|#1e3a5f}"];
    files [label="前端解析文件\n标识去重、多选录像"];
    times [label="前端分配上传时间\n按完成时间排序后倒推"];
    prepare [label="获取或创建录像来源参赛者\ncreate_history_participant", fillcolor="${#dbeafe|#1e3a5f}"];
    bind [label="逐个请求绑定标识\nbind_history_identifier\n归属冲突只跳过绑定", fillcolor="${#dbeafe|#1e3a5f}"];
    upload [label="逐文件代传\nupload_history_video", fillcolor="${#dbeafe|#1e3a5f}"];
    associate [label="创建或复用录像\n显式加入本届比赛", fillcolor="${#dcfce7|#14532d}"];
    inspect [label="复用比赛信息和成绩接口刷新列表\n核对结果，保留失败文件供重试"];
    recalculate [label="人工逐届重算\nrefresh_tournament_scores", fillcolor="${#fef3c7|#713f12}"];
    results [label="读取公开成绩\nget_results", fillcolor="${#dbeafe|#1e3a5f}"];

    info -> participants [label="取得比赛 ID 和结束时间"];
    participants -> files [label="核对本届参赛者"];
    files -> times [label="只保留选中标识的文件"];
    times -> prepare [label="order、user_id"];
    prepare -> bind [label="返回 participant_id"];
    bind -> bind [label="每次一个标识，顺序请求", style=dashed, constraint=false];
    bind -> upload [label="全部标识处理完成后"];
    upload -> associate [label="file、带时区的 upload_time"];
    associate -> inspect [label="返回录像 ID、审核状态"];
    inspect -> upload [label="只重试未成功文件", style=dashed, constraint=false];
    inspect -> recalculate [label="核对后使用 tournament_id"];
    recalculate -> results [label="整场结果更新完成"];
}
```

### 准备与标识绑定

`HistoryVideos.vue` 在浏览器解析录像，展示去重后的玩家标识，由管理员多选。只上传选中标识对应的文件；这里使用的是录像内的玩家标识，不是比赛 token。

`create_history_participant` 在 API 事务内按届数和用户 ID 查询并锁定比赛、目标用户，完成权限和比赛状态校验；`prepare_gsc_history_videos` 接收这两个模型对象，返回本届该用户已有的 `manual_scores=false` 参赛者，不存在则创建。已有手工成绩来源仍拒绝，不自动切换来源。复用不保存 participant，不改变原成绩、排名积分、标识、token、参赛窗口或录像关联；也不触发创建和 best 保存信号。它不接收操作者或标识列表，也不执行绑定。新建时使用默认成绩，创建信号不会自动回填历史录像，但仍为站内用户补建默认 `TournamentUser`，并正常用当前 `t37` 尝试改善 best。

前端拿到 participant ID 后，按选择顺序逐个调用 `bind_history_identifier`。每个请求只接收一个 `identifier`，API 重新检查实际比赛权限、AWARDED 状态及录像来源 participant，再将 participant 对象传给 `bind_gsc_history_identifier`，由 service 注册标识并调用 `identifier.services.bind_identifier`。绑定会刷新既有录像及排行，不能将多个标识打包进同一请求：

- 新标识先注册；未绑定或已属于目标用户的标识沿用绑定业务，目标用户已有的相应 `IDENTIFIER` 录像也可转为 `OFFICIAL`。
- 已属于其他用户的标识返回 `bound=false`，不转移归属，其他标识继续处理。
- 可绑定但不安全的标识令本次绑定请求失败并回滚，不当作可忽略的归属冲突；之前创建的 participant 和成功绑定的其他标识保留。

所有选中标识均返回绑定结果后才逐文件上传。绑定失败则暂停，不继续绑定后续标识或上传；本页重试跳过已收到结果的标识（包括归属冲突），从未完成步骤继续。后续文件失败不会撤销此前已提交的 participant 或标识绑定。上传时仍独立校验文件标识，不能因为绑定阶段出现过归属冲突，就让对应录像参与计分。

### 上传时间

时间锚点默认是比赛信息接口返回的比赛结束时间，也允许管理员修改。前端只对选中的文件按原始完成时间升序稳定排序，完成时间相同则保留选择顺序，然后分配：

```text
最后一个文件：upload_time[n] = 锚点
更早的文件：  upload_time[i] = upload_time[i+1] - timems[i+1]
```

`timems` 以毫秒为单位。每个文件携带最终算好的带时区时间，后端不重新排序、不统一回退到比赛结束时间。重试使用首次分配的时间，不重新计算。

## 上传 API 内部流程

API 在事务内完成权限、比赛状态和录像来源检查，将 participant 对象交给 `tournament.gsc.services.upload_gsc_history_video`。service 独立编排解析、标识校验和查重，直接调用 `VideoModel.create_from_parser`，不接收操作者、不调用 common 的普通上传流程。两条流程分别维护标识和查重政策，仅复用解析器、标识基础能力、文件比较与上传时间保存工具。

```dot
digraph gsc_history_upload {
    graph [layout=dot, rankdir=TB, bgcolor="transparent", nodesep=0.4, ranksep=0.5, splines=polyline];
    node [shape=box, style=filled, fillcolor="${#f1f5f9|#1f2937}", color="${#94a3b8|#64748b}", fontcolor="${#0f172a|#e5e7eb}", fontsize=12];
    edge [color="${#64748b|#94a3b8}", fontcolor="${#475569|#cbd5e1}", fontsize=10, arrowsize=0.7];

    request [label="upload_history_video\n单文件 + 带时区上传时间", fillcolor="${#dbeafe|#1e3a5f}"];
    guard [label="API 事务内检查比赛权限、状态\n要求站内用户、非手工成绩参赛者", fillcolor="${#dbeafe|#1e3a5f}"];
    parse [label="MSVideoParser\n拒绝未完成录像，保留审核结论"];
    identifier [label="检查标识安全与归属\n合法录像标识不匹配则为 IDENTIFIER"];
    duplicate [shape=diamond, label="find_identical_video\n是否存在相同文件？"];
    owner [shape=diamond, label="文件是否属于\n目标用户？"];
    conflict [label="409：拒绝归属冲突\n不修改原录像和上传时间", fillcolor="${#fee2e2|#7f1d1d}"];
    reuse [label="复用既有 VideoModel\n仅当请求时间更早时保存", fillcolor="${#dcfce7|#14532d}"];
    create [label="create_from_parser\n创建录像并传入 upload_time", fillcolor="${#dcfce7|#14532d}"];
    save_time [label="set_import_upload_time\n创建后覆盖 auto_now_add"];
    link [label="tournament.videos.add(video)\n显式关联历史比赛，M2M 去重", fillcolor="${#dcfce7|#14532d}"];
    response [label="返回 VideoBaseOut\n成功入库不等于 OFFICIAL 或已计分", fillcolor="${#dbeafe|#1e3a5f}"];

    request -> guard -> parse -> identifier -> duplicate;
    duplicate -> owner [label="存在"];
    duplicate -> create [label="不存在"];
    owner -> conflict [label="否"];
    owner -> reuse [label="是"];
    create -> save_time -> link;
    reuse -> link;
    link -> response;
}
```

- 文件比较按文件大小筛选，再比较完整内容；同用户重复文件保留 `min(原上传时间, 请求上传时间)`，不会重复创建录像。任何新建或提前保存时间的操作仍走正常保存信号。
- 创建前传入来源时间，供 `pre_save` 自动 check-in 使用，避免按当前时间误入其他正在进行的比赛；创建后仍须显式保存，以覆盖 `auto_now_add`。
- 本届历史关联由上传 service 显式建立，不要求 token、参赛窗口或 participant 的 `arbiter_identifier` 与文件一致。不修改录像内原始完成时间，也不改变文件归属。
- 完成性、标识不安全等业务错误在 GSC API 层转换为错误 HTTP 状态，不让前端把历史默认的 HTTP 200 错误响应当作上传成功。成功响应的 `state` 仍可能不是 `OFFICIAL`。

## API 职责

下表是业务角色索引，不替代自动生成的请求与响应文档。历史写入接口位于 `tournament.gsc.api`；读取直接复用现有比赛信息和公开成绩 API，删除入口复用 `tournament.api`。

| API | 角色与主要结果 |
| --- | --- |
| `GET /api/tournament/gsc/admin-info?order=...`（`get_GSC_tournament`） | 按届数取得父表比赛 ID、起止时间和状态；前端使用结束时间作为默认时间锚点，再以比赛 ID 请求成绩，组合成管理列表。 |
| `POST /api/tournament/gsc/history/prepare`（`create_history_participant`） | 获取或创建录像来源 participant，不接收标识列表、不绑定标识。本届已有非手工记录则原样返回，手工来源仍冲突，不覆盖或切换来源。 |
| `POST /api/tournament/gsc/history/participants/{participant_id}/identifier`（`bind_history_identifier`） | 每次注册并绑定一个标识，返回 `identifier` 和 `bound`。归属冲突返回 `bound=false`，其他错误使本请求失败；每个请求独立事务，前端顺序执行。 |
| `POST /api/tournament/gsc/history/participants/{participant_id}/videos`（`upload_history_video`） | 每次处理一个文件：解析、标识校验、查重、创建或复用、保存上传时间、关联比赛；返回录像及审核状态。每个请求一个事务。 |
| `POST /api/tournament/gsc/history/scores/users`（`import_history_user_scores`） | 为有站内账号但录像缺失的选手录入九项成绩，创建 `manual_scores=true` 的 participant，不从录像计算。 |
| `POST /api/tournament/gsc/history/scores/anonymous`（`import_history_anonymous_scores`） | 以 Arbiter 标识创建匿名手工成绩选手，不虚构站内用户、不绑定账号；与站内选手一起占用实际名次，但不获得账号积分。 |
| `DELETE /api/tournament/participant/{participant_id}`（`delete_participant`） | 删除没有任何关联录像的参赛者；有非 OFFICIAL 或不计分录像也拒绝。删除信号撤回本人已发积分并更新 best，但不重排其他人。 |
| `GET /api/tournament/gsc/results?tournament_id=...`（`get_results`） | 已颁奖比赛的公开成绩读取入口，同时用于管理列表及补录、删除后的刷新；已有 `manual_scores`、`has_videos` 等字段。只读当前保存的结果，不触发计算。 |

两种 CSV 由前端解析，按 `order` 分组，每次提交同届 1～10 条 JSON 记录，不上传 CSV 原文件。站内用 `(order, user_id)`、匿名用 `(order, arbiter_identifier)` 标识参赛者；两种身份不混合。一个请求内任意记录失败则整批回滚，之前成功的请求保留；前端顺序提交，失败后不再提交后续批次。

CSV 使用 UTF-8（允许 BOM）及表头，列顺序不限；身份字符串保留大小写和空格。九项成绩为整数毫秒，不检查分项之间的大小或总和关系；`t37` 由数据库计算，文件不包含排名或积分。两类表头如下，示例位于 `front_end/cypress/fixtures/gsc/type2.csv` 和 `type3.csv`：

```csv
order,user_id,bt1st,bt20th,bt20sum,it1st,it12th,it12sum,et1st,et5th,et5sum
order,arbiter_identifier,bt1st,bt20th,bt20sum,it1st,it12th,it12sum,et1st,et5th,et5sum
```

站内用户必须存在，匿名标识必须非空。同一身份可跨届复用，但同届已有 participant 或文件内同届重复身份均拒绝，不覆盖、不自动切换成绩来源，也不删除文件未列出的选手。需要更正时先按无录像规则删除，再重新添加。每批最多 10 条只是请求上限，不保证生产环境的 2 秒响应时限。

## 重试与人工重算

前端分别记录 participant ID、已处理的标识及逐文件上传结果。绑定失败先暂停，重试时不重复处理已收到结果的标识；所有标识完成后，录像上传按文件记录结果，单文件失败后继续处理其他文件，只重试未成功文件并保留原上传时间。准备请求超时可直接重试，已提交的录像来源 participant 会原样返回，不会重复创建。页面刷新后需重新选择文件，准备接口仍可复用已有录像来源记录；手工来源不能用此方式接管。绑定超时可对同一标识重试，已属于本人时沿用原绑定业务，不转移他人标识。

维护时备份数据并暂停结算、best 和年度积分缓存维护等相关写任务，完成材料补录并核对后，在 `back_end/saolei` 逐届执行：

```bash
python manage.py refresh_tournament_scores <tournament_id>
```

这里使用管理列表给出的父表比赛 ID，不是 `order`。命令在事务内依次补齐 `TournamentUser`、重算录像来源成绩、刷新全部排名、按新旧 `rank_score` 差额修正积分、重建个人 best 并更新排行缓存。录像计分只接受 `OFFICIAL`、STD（含 NF）、标准三级及对应的 3BV/用时条件；手工来源保留输入的九项成绩，匿名选手占名次但不写账号积分。

GSC 的 `manual_scores` 按参赛者设置，同场可以混合两种来源。普通删除录像不立即重算；后续执行本命令时，录像来源中已删除录像的成绩贡献作废，从剩余合格录像或默认值补位。手工来源保留主办方输入的九项成绩，但名次和积分仍可能随全场重排变化；不能仅因录像缺失自动改为手工来源。

删除后重新添加的记录也要逐届重算，以修正其他选手的排名和积分。删除本人积分时使用原比赛结束时间计算衰减；不能用删除后的新记录覆盖旧 `rank_score` 而省略撤分。普通 finish 任务不是历史维护的替代入口。

相关实现：`tournament/gsc/api.py`、`tournament/gsc/services.py`、`tournament/management/commands/refresh_tournament_scores.py`；前端为 `components/GSCAdmin/HistoryImport.vue`、`HistoryVideos.vue`、`HistoryScores.vue` 和 `history.ts`。

更多信号与维护细节见[信号触发关系](./signals.md)、[缓存结构](./cache.md)及[管理命令](./management-commands.md#refresh-tournament-scores)。
