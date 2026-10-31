# 个人主页

## 路由与职责

`App.vue` 加载个人资料并提供顶级 tab，路由组件置于 `keep-alive` 中。默认进入 `/player/:id/top`，旧 `/summary` 链接重定向至 top。

| tab | 路由组件 | 数据与展示 |
| --- | --- | --- |
| top | `UserTopView.vue` | `TopSummary.vue` 请求完整 top 纪录、读取 Pinia 锚点；`TopRadar.vue`、`TopRecordTable.vue` 只渲染 props |
| PB | `UserPBView.vue` | 一次获取用户全部 PB，`PBRecordGrid.vue` 按等级展示网格 |
| 纪录 | `UserRecordView/App.vue` | 扫雷网、Thrp 及自定义 pluck 纪录 |
| 账号关联 | `UserAccountLinkView.vue` | 外部账号关联 |
| 录像 | `UserVideoView.vue` | 全部可见录像、日历/BV 选择、表格/散点图 |
| 上传、设置 | `UserUploadView.vue`、`UserSettingsView.vue` | 仅本人可见；设置包含资料编辑和标识管理 |

top 和 PB 的业务规则、缓存与接口统一见 [竞速排行榜 README](../../../../back_end/saolei/speedranking/README.md)，此处仅说明页面职责。

## 请求生命周期

- top、PB、设置均不下载完整录像；只有录像 tab 激活且数据失效时才请求 `videolist`。切换本地展示或返回有效缓存不重复下载。
- 页面有效性同时受激活路由、用户 id、登录会话及 `profileDataRevision` 约束。失活页面不为新玩家后台加载；过期响应不得覆盖当前玩家或清除新请求的 loading。
- 上传、标识变更通过 `profileDataService` 使相关页面数据失效，下次激活再刷新。退出或切换账号时丢弃旧身份的私有录像。
- `useProfileVideos.ts` 管理录像缓存，完整结果保存在用户页面数据中，不存入资料 IndexedDB。`userService.ts` 的 pending Promise 合并只去重并发请求，不代替结果缓存。
- 头像和签名资格读取普通扫雷网 `et`，不扫描完整录像或用 PB 最小值替代。资格查询区分加载、失败和未达标，设置页保留重试及后端最终校验。

## top 展示

- 普通/NF 各一块，每块上方雷达图、下方九项成绩表。两块用 CSS grid 自适应并列或上下排列；宽表在自身容器内横向滚动。
- 两图共用一次用户完整纪录请求，锚点直接读取 Pinia 的 `store.topAnchors`，由首次访问的 `/api/common/loginauto` 完整加载，个人页不再请求锚点。各图只使用本榜主要锚点，归一化为 100；Time 反比、Bvs 正比，Stnb 取 iqg 比值的 `1/1.7` 次方。Stnb 数值展示时乘等级系数，空锚点取半径 0。
- 雷达图由 `TopRadar.vue` 直接绘制 SVG，不显示标题或 legend，NF 图中央显示半透明 NF。纬线按定阶节点布置，只保留到玩家最高成绩外侧的第一圈；超过最高节点不新增节点，缩放同时容纳成绩与锚点。环带复用用户的定阶配色，半透明且不叠色；图形主题样式使用 `--ui-*`。
- 每张雷达图共用一个跟随鼠标的 Tippy：轴线优先响应并高亮，提示依次为定阶、成绩、锚点成绩；环带只提示定阶称号，空白处及离开图表时隐藏。定阶文案统一使用全局 `ranking.grade`。
- 顶部 LSF 堆叠条复用 `StackBar`，六段分别为普通/NF 的初、中、高级加权贡献，数值显示两位小数，段宽使用原始数值。级别色读取全局配置，NF 使用半透明色。刷新按钮位于堆叠条右侧，只重新读取用户纪录，不请求锚点、不触发后端重建；重载网页才更新锚点。
- 成绩表按等级合并三行，从真实 top5 计算均值，列出均值和五条成绩；不依赖 API 返回 `mean`。缺项显示缺省值但不生成录像链接；真实录像复用 `VideoPreviewLink`。锚点失败不阻断成绩表。

## PB 展示

- 用户全部 PB 按 `(nf, level, bv)` 索引；普通/NF 和 `time / bvs / stnb / rank` 在本地单选切换，不追加请求。
- 每级别网格每行十格，按已有最小/最大 BV 向十位补齐。无纪录格子留空，整级别无纪录时显示空态；有纪录的格子预览同一条 PB 录像，不因指标变化重新选录像。
- `rank=null` 显示 `--`，不丢弃已有录像；原生 `title` 展示时间、派生指标和排名，不逐格预取详情。
- rank 前三名采用不透明金银铜和固定深色文字；4–10、11–50、51–100 名采用主题蓝的 22%、14%、7% 背景，之后及缺失排名无填色。后续排名文字使用主题色，不降低整格或链接透明度。

## Thrp 纪录

纪录 tab 的 `ThrpCard.vue` 接收用户 id，单次请求 `/api/effranking/thrp/player/{id}` 获取完整纪录与排名。按初、中、高级、sum、高级 NF 的顺序始终展示五列，格式为三位小数成绩加括号排名，缺项或缺失排名显示 `--`。高级 NF 多局时以 `details` 的 `1 x N` summary 收起显示，展开后才创建逐局预览链接；只有一局时直接展示该局链接。高级 NF 独立于 sum，sum 仅按普通三项缺项 0 求和，不生成录像链接。成绩与展开逻辑由 `components/visualization/ThrpRecordValue.vue` 统一处理，与 Thrp 排行榜共用。

请求复用 `profileDataService` 的个人页缓存与失效通知，用户切换或失活后不接受旧响应。全局上色启用时使用 IOE 共用色阶，sum 固定按总值除以 3 上色。组件测试位于 `UserRecordView/ThrpCard.cy.ts`。

## 录像选择与展示

- 初始上方不显示可视化，下方显示表格。上方可选日历/BV 表，下方可选表格/散点图；散点图不依赖实验开关。
- 数据链为完整可见录像 → 日期/BV 选择 → 共享筛选 → 表格或散点图。上方始终统计完整录像，下方两种展示使用相同筛选结果；表格分页不截断散点图输入，CSV 仍导出原有完整个人数据。
- 日期使用浏览器本地年月日；结束日期模式沿用 `end_time ?? upload_time`。切换日期来源时清除日期选择，允许选择空日期。
- BV 选择使用完整 `(level, bv)` 桶，包含各模式、软件及状态。BV 表自己的代表录像筛选仅影响上方展示，不缩窄下方成员；下方共享筛选也不改变上方分布。
- 选择状态仅保存日期或 BV 键，不复制录像数组。重复点击或清除恢复全集；切换上方概览清除选择，切换下方展示保留选择、筛选和有效展示状态。用户或身份变化时重置；刷新后不存在的 BV 桶取消选择。
- 范围或共享筛选变化后表格回到第一页。主要日历/BV 操作只选择，不同时打开播放器；独立预览保留，其他未启用选择的调用方仍可直接预览代表录像。日期/BV 支持键盘选择和主题选中边框。
- 本人公开比赛录像沿用共享确认弹窗，成功后只更新该录像，失败保留状态供重试；其他用户和访客仍受后端可见性限制。

## Arbiter CSV 本地记录

- 本人录像 Tab 第一行的“导入CSV”按钮与导出数据并列，选中后在下方展开文件选择、清除和提示；收起不清除本地记录。支持 Arbiter 的 `stats_csv.csv`，`BEG/INT/EXP` 对应初、中、高级。只比较 CSV 独有录像，不提供独立 diff 页面。
- 匹配使用日期六列编码的秒级结束时间和整数毫秒 `Time`，与 AVF 解析结果对齐，不按浏览器时区修正，不用上传时间替代。等级、3BV、软件、模式及点击统计不同只提示，不否决匹配；CSV 同键行合并。
- CSV 独有记录用 `MS_State.Local = 'l'`、`id=0` 表示，行键由匹配键生成，参与现有筛选、分页、日历、BV 表及散点图；成绩可见，上传时间/文件大小显示 `—`，不提供服务器录像操作。
- 服务器录像缓存保持原样，CSV 不进入数据库、IndexedDB、导出、上传计数或排行榜。LOCAL 不能作为服务器查询状态。
- 每次重新导入或比较先清除全部 LOCAL，再重新生成；导入失败不恢复旧集合。服务器录像更新后使用当前 CSV 重算，已上传的匹配记录不再生成 LOCAL。
- CSV 只保留在当前页面实例内存中；同一用户切换 Tab 可保留，页面重载/销毁、切换用户或登录身份变化时清除。文件大小限制 10 MiB，最多 100,000 行。
- 必填列为 `Day/Month/Year/Hour/Min/Sec/Time`；文件缺少必填表头、重复表头或引号结构错误时拒绝导入。非法日期或用时所在行跳过，附加统计不合法时按缺失值展示并提示。

导入使用 Papa Parse，现有 jtcsv 导出保持原样。选型时验证了 `jtcsv@5.0.0/browser`：重复表头会覆盖前值，多余字段被丢弃，缺列不提供结构化错误，因此不能直接用于校验导入数据。Papa Parse 能保留原始单元格并报告解析错误；当前实现按行数组读取，自行校验表头与业务字段，不另写 CSV 分词器。参考 [Papa Parse 官方文档](https://www.papaparse.com/docs)。

样本 `stats_csv.csv` 与同目录 AVF 已核对：CSV 日期为 `2023-10-05 21:25:57`，AVF 结束时间为 `2023-10-05T21:25:57.244Z`，两者用时均为 `35090ms`。匹配忽略小数秒，Path 和 BBBVs 的舍入不参与匹配。

## 验证

- `App.cy.ts`：顶级 tab、默认入口、按需加载及设置权限。
- `TopSummary.cy.ts`：LSF 总值与六段构成、普通/NF 共享纪录与 Pinia 锚点、表格明细、失活隔离及纪录失败重试。数值权重在 `topRankingService.test.ts` 验证，段宽与数值格式化在 `StackBar/App.cy.ts` 验证，不在个人页重复测试。
- `UserPBView.cy.ts`：指标/NF 切换、rank 配色、空态、重试及请求生命周期。
- `useProfileVideos.test.ts`、`videoSelection.test.ts`：身份与修订号失效、过期响应、日期/BV 选择及共享筛选。
- `arbiterCsv.test.ts`、`arbiterCsvDiff.test.ts`、`useArbiterCsvDiff.test.ts`：真实 CSV 样本、异常输入、匹配与去重、LOCAL 展示数据和重建生命周期；`UserVideoView.cy.ts` 覆盖 CSV 导入、收起、清除及混合展示。
- `UserVideoView.cy.ts` 与日历/BV 组件测试：选择联动、正式散点图、分页及公开操作；`cypress/e2e/profile.cy.ts` 保留真实后端流程验证。

```powershell
# 在 front_end 目录运行
npx.cmd vitest run src/services/topRankingService.test.ts src/services/pbRankingService.test.ts src/views/UserView/useProfileVideos.test.ts src/views/UserView/videoSelection.test.ts
npx.cmd cypress run --component --browser chrome --headless --spec "src/views/UserView/App.cy.ts,src/views/UserView/TopSummary.cy.ts,src/views/UserView/UserPBView.cy.ts,src/views/UserView/UserVideoView.cy.ts"
npx.cmd vitest run src/views/UserView/arbiterCsv.test.ts src/views/UserView/arbiterCsvDiff.test.ts src/views/UserView/useArbiterCsvDiff.test.ts
```

Cypress 由开发者运行。实际雷达图尺度、宽窄布局和深浅主题需浏览器验收，不能用编译或静态检查通过替代。
