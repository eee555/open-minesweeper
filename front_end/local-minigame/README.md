# 小游戏开发与离线构建

网站和离线版共用三种训练。网站登录且未封禁的玩家成功通关后，可点击按钮提交用时及回放，各模式保留个人最佳及对应回放，公开排行榜位于 `/#/ranking/minigame`，无需实名；离线版只保留本地历史。在线使用指南见 [VitePress 中文页](../../vitepress_doc/zh/guide/minigames.md)及[英文页](../../vitepress_doc/en/guide/minigames.md)。离线帮助维护在 [README.txt](./README.txt)，版权及灵感来源维护在 [COPYRIGHT.txt](./COPYRIGHT.txt)，两份正文同时用于离线页面和 ZIP。[后端实现](../../back_end/saolei/minigame/README.md) 单独维护成绩与排行方案。

| 游戏 | 网站入口 | 规则与生成器 |
| --- | --- | --- |
| 左键训练 | `/#/minigame/left-click` | [leftClickTraining.ts](../src/utils/minigame/leftClickTraining.ts) |
| 标双训练 | `/#/minigame/flag-chord` | [flagChordTraining.ts](../src/utils/minigame/flagChordTraining.ts) |
| 漏雷训练 | `/#/minigame/missing-cell` | [missingCellTraining.ts](../src/utils/minigame/missingCellTraining.ts) |

## 公共显示与输入

[MiniGame 组件](../src/components/MiniGame/) 复用项目的 `@putianyi888/vue3-minesweeper-board`，不使用 `ms-toollib`。游戏控制器维护规则、状态与整数毫秒成绩；[clock.ts](../src/utils/minigame/clock.ts) 负责计时，依赖库的 `Counter` 仅显示剩余数量和秒数（三位小数）。

[Frame.vue](../src/components/MiniGame/Frame.vue) 使用依赖库 Example 的外框布局，计数器栏可点击或用 Enter／空格重开。[Board.vue](../src/components/MiniGame/Board.vue) 通过公开的背景、前景插槽显示按下预览和透明雷，叠加轨迹及目标高亮。前景透明度不影响背景按下状态。

主棋盘显示编码为：`0` 空白压下、`1..8` 数字、`10` 盖住、`11` 旗、`14` 错旗、`15` 爆雷、`16` 凸起雷。直接传给 `BoardForeground` 的矩阵使用另一套编码（雷为 `-1`、旗为 `-2`），不能把主棋盘矩阵直接作为前景矩阵传入。预览只派生背景副本，不修改游戏状态。依赖升级时可对照上游 [Example 源码](https://github.com/putianyi889/minesweeper-board/blob/d23319a832c443be9fbfccca65de17936f94a8ca/docs/components/MinesweeperExample.vue) 核对公开接口。

输入统一经过 [ClassicMouseAutomaton](../src/utils/classicMouse.ts)，依据[经典操作模式说明](../../vitepress_doc/zh/guide/minesweeper/mouse-event.md)：右键按下输出插旗，左键弹起输出单击，双键首次弹起输出双击。适配层从当前事件坐标定位，覆盖棋盘外松开、失焦和取消；不依赖上次 `mousemove` 缓存的格子，也不重复监听 `click`。单键按住预览当前格，双键预览周围 3×3；旗格保持凸起。装饰图层不拦截输入。

[settings.ts](../src/utils/minigame/settings.ts) 集中管理 `minigame-settings` localStorage，兼容旧配置补默认值。所有游戏共用格子大小（默认 32px）和重开热键（默认未设置），左键雷不透明度默认 50%。网站设置页与小游戏页底部共用设置组件；修改显示参数保留当前局。玩法参数保持在棋盘上方，修改时重开。

## 标双题目排布

每题只有一个雷，控制器用单个 `mine` 索引保存雷位；级别与题数见使用指南。

继续按固定题数递归切分棋盘矩形，每次随机选择容量足够的切分和题数分配；每个叶子区域放一道完整 3×3 题。中级的 15 题直接随机散布，无需碰撞重试或生成满盘后删题，不要求所有合法排布等概率。每题从八个邻格中随机选择一个雷位。

此前调查的 [potpack](https://github.com/mapbox/potpack) 面向近正方形容器中的紧凑装箱，不能直接满足固定棋盘上的随机散布；因此此处保留容量约束分区。Vitest 覆盖两个固定级别及不同随机源下的题数、单雷、边界、非重叠和实际位置变化。

## 漏雷目标唯一性

生成器知道雷阵和唯一未打开的安全格 `s`。令 `V(x)` 为 `x` 周围已打开格子的**绝对坐标集合**，目标格与棋盘边界之外不算已打开。

如果有雷 `m` 满足 `V(m) = V(s)`，互换两格的雷／安全身份后，所有可见数字、未打开位置和总雷数不变，产生歧义。反之，未打开格中仅有一个安全格，其他解释必对应这样的互换；不存在此类雷即为唯一可判断。

- `V(s)` 非空时，只需检查切比雪夫距离不超过 2 的雷。
- `V(s)` 为空时，必须检查全盘雷，覆盖远处包心雷的歧义。
- 比较坐标集合，不能比较数字值集合。
- `isValidMissingCellTarget` 另排除邻接 0 的目标，允许目标本身为 0。

生成器随机排列固定数量的雷及安全格，逐个检查候选目标；没有合格目标就重生成，最多尝试 64 个雷阵，异常随机源耗尽尝试时抛错并保持原游戏状态。测试使用独立的可见数字约束求解，穷举全部 3×3 雷阵及安全目标交叉验证判据，并覆盖远处包心雷与零邻格限制。

## 回放与分析

棋盘压缩、事件数组、像素坐标和差分编码使用回放数据格式 v1，见[中文标准](../../vitepress_doc/zh/guide/development/minigame-replay-format.md)及[英文标准](../../vitepress_doc/en/guide/development/minigame-replay-format.md)。新回放统一保存为 v1，读取时兼容无版本字段或显式 `version: 0` 的旧数据。

左键训练和标双训练结束后提供当前局回放；重开或切换游戏清空当前预览，成功局的记录保留在本地数据库，暂不提供录像文件下载。

- [boardEncoding.ts](../src/utils/minigame/boardEncoding.ts) 编解码 Base64 雷位及标双题目；[recording.ts](../src/utils/minigame/recording.ts) 负责格式读取、v0 转换、差分事件解码，并通过原有自动机推导按键状态和操作意图。
- [archive.ts](../src/utils/minigame/archive.ts) 复用 [7z-wasm](https://github.com/use-strict/7z-wasm) 将 v1 JSON 压缩为只含 `replay.json` 的独立 7z，使用 LZMA2、级别 1 和 1 MiB 字典。压缩器按需初始化，离线包内联 Wasm；虚拟文件在每次操作后清理。
- [replay.ts](../src/utils/minigame/replay.ts) 集中管理记录与外观：全长轨迹保留至当前位置，遮罩不透明度 0，marker 为 0.25 格。保存时使用整数像素及开局固定的 `cellSize`，渲染时换算为格子单位，不受显示尺寸变化影响；旧数据迁移为 `cellSize: null`，按固定参考值 32 解码。
- [useTrainingReplay.ts](../src/utils/minigame/useTrainingReplay.ts) 复用现有 `usePlayback` 时钟。拖动恢复原播放状态，末端停止；图表悬停临时定位，移开恢复。按事件索引区分同一毫秒内的操作。
- [replayAnalysis.ts](../src/utils/minigame/replayAnalysis.ts) 使用最近 1 秒窗口计算移速／点击速度，开局前补零，每 50ms 及标双触发点采样。左键时长排除首次点击、取消及双键，用 `d3-array` 按固定 10ms 分桶，边界值计入右桶。
- 成功标双统计该题最后插旗、成功双键前最近左键按下、成功双键触发三个时间点。纠正错旗后使用该题最后一次插旗时间；失败及无效果的双键不计入。底段为插旗至左键按下，顶段为左键按下至双键触发。
- 共享分析组件复用 `vue3-plots` 和 Tippy；漏雷结果复用原有 StackBar，并关闭其 tooltip。图表不改变游戏记录。

## 本地成绩

[history.ts](../src/utils/minigame/history.ts) 使用已有的 `idb`，在每局成功结算时自动保存一条记录；失败、未完成的重开及切换游戏不保存，回放和悬停不重复写入。在线和离线入口共用此逻辑，暂不提供历史列表或历史可视化。

数据库为 `saolei-minigame`，结构版本 3，`results` 表使用自增 `id`，保存游戏类型、完整模式参数、完成时间 `playedAt`（Unix 毫秒）和成绩 `scoreMs`（整数毫秒）。两条非唯一索引分别为 `playedAt` 和 `scoreMs`，支持时间与成绩排序；同一毫秒完成或成绩相同的多局均保留。版本 1 的 v0 和版本 2 的 v1 JSON 旧库均在升级事务中自动转换为 7z，保留主键、时间、成绩、模式和索引；转换失败时回滚整个升级并保留旧库。压缩器在打开升级事务前初始化。

- 有旧记录需要转换时，网站和离线版共用 [HistoryMigration.vue](../src/components/MiniGame/HistoryMigration.vue)，显示“正在优化录像格式，请不要关闭页面”、进度条和已处理／总条数。升级提交或失败回滚后关闭，期间不允许按 Escape 或点击遮罩关闭。压缩前先留出绘制提示的时间，并用轻量数据库请求保持升级事务活跃。
- 三种游戏统一将 7z `ArrayBuffer` 保存到条目的 `replay`，不转 Base64，也不保存展开的快照和统计。`readMinigameHistoryEntry` 解压并还原供运行时使用的成绩结构。
- 左键及标双载荷为 `TrainingRecording` 的 `version`、`cellSize`、压缩初始棋盘 `initialBoard`、普通事件 `events` 及特殊事件 `specialEvents`。读取后调用 `rebuildTrainingReplay({game, mode}, recording, scoreMs)`，复用游戏规则一次性重建全部快照、剩余计数及成功标双时间点，再交给现有回放组件；这些派生数据只留在内存中。
- 漏雷载荷为 `version: 1` 和 10 局的雷位字符串、目标坐标及耗时。解压后由 `decodeMissingCellRounds` 重算数字并还原运行时棋盘，再交给 `reviewMissingCellRound` 逐局回溯。
- 写入前立即复制数据，异步打开数据库期间重开不会改变待保存内容。`idb.add` 等待事务完成；保存失败记录控制台警告，不中断当前对局，后续成绩仍会尝试写入。
- 本地历史独立于可丢弃的 `saolei-cache`，不套用缓存的过期、版本清空或自动字段转换。以后修改结构时显式迁移并保留历史数据。连接在版本升级时释放，避免旧页面阻塞迁移。
- 数据归属于当前浏览器与来源，在线站点和离线文件不保证共用；清除浏览器站点数据会删除记录。

网站入口收到游戏的 `completed(rankingKey, scoreMs, replay)` 事件后暂存本局数据，通过 `result-actions` 插槽在棋盘下方提供上传按钮，仅在点击时提交；重开、修改玩法参数或切换游戏清除待上传状态。HTTP 和登录状态仅由网站 `MiniGameView/App.vue` 引入。左键及标双提交完整 `TrainingRecording`，漏雷提交 `{version: 1, rounds}`；表单中的 `replay` 为 JSON 字符串。后端压缩为 7z 后用 BinaryField 保存每人每榜最佳成绩对应的回放，回放不进入 Redis。上传失败可重试，不影响自动保存的本地记录；失败局不发完成事件。离线入口不监听这些事件，继续禁止导入网站 HTTP、用户 store 及路由。

## 构建与资源

在 `front_end` 运行：

```powershell
npm.cmd run build:offline:minigame
```

版本唯一来源为 [version.json](./version.json)，更新记录见 [CHANGELOG.md](./CHANGELOG.md)。生成：

- 展开目录：`dist-offline-minigame/`
- ZIP：`OpenMinesweeperMinigames-${version}.zip`
- 网站下载副本：`public/assets/OpenMinesweeperMinigames-${version}.zip`

解压后用 Chrome 或 Edge 直接打开 `index.html`，无需服务或联网缓存。中英文、主题和设置均由离线入口提供。

`vite.minigame.config.ts` 复用现有 Vite、`vite-plugin-singlefile` 及共享的 `scripts/offline-build.ts`，内联脚本、CSS、棋盘 SVG、PrimeIcons WOFF2 及 7z Wasm，并在合并前收集依赖许可。构建禁止导入网站 HTTP、用户 store、路由、入口初始化及 `ms-toollib`。打包脚本复用 `scripts/offline-package.mjs`，校验无外部资源且压缩器已内联，附带项目和依赖完整许可及 7z／unRAR 许可文件。产物由 Git 忽略。

`npm.cmd run build:offline` 同时生成 Analyzer 与小游戏包；现有网站 dev/build 的 pre hook 会先生成两种 ZIP，再将 `public/assets` 复制到网站产物。直接调用 Vite CLI 前应手动生成离线包。Analyzer 版本独立维护；本地构建不创建 Release 或上传文件。

## 验证

```powershell
node --test scripts/offline-package.node-test.mjs
npx.cmd vitest run src/utils/classicMouse.test.ts src/utils/minigame src/services/minigameRankingService.test.ts src/views/RankingView/useRankingQuery.test.ts
```

组件检查由用户执行：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/MiniGame/*.cy.ts,src/views/MiniGameView/**/*.cy.ts,src/views/RankingView/MinigameRanking.cy.ts,src/views/SettingView/MiniGame.cy.ts,src/views/Menu.cy.ts"
```

Cypress 由用户执行。构建与 ZIP 校验不能替代真实断网 `file://` 验收；关闭网络后检查三种游戏、纹理、计时、回放／图表、重开、设置、主题及语言，并确认没有网络请求。
