# VideoAnalyzer

项目内可复用分析组件，入口为 `src/components/VideoAnalyzer/index.ts`。子组件、解析、采样、播放、主线程导出及对应测试都在本目录；站内包装和后续事项位于 `src/views/VideoAnalyzerView/`。

```vue
<VideoAnalyzer v-model:config="config" v-model:probability-color-scheme="probabilityColorScheme" v-model:exporting="exporting" :source="source" title="录像分析">
    <template #info>调用方提供的信息</template>
</VideoAnalyzer>
```

```ts
import { ref, shallowRef } from 'vue';
import VideoAnalyzer, { defaultAnalyzerConfig } from '@/components/VideoAnalyzer';
import type { ReplaySource } from '@/components/VideoAnalyzer';

const source = shallowRef<ReplaySource | null>(null);
const config = ref(defaultAnalyzerConfig());
const probabilityColorScheme = ref({ colors: ['#15803d', '#dc2626'], thresholds: [50] });
const exporting = ref(false);
// 调用方获取字节后，替换 source.value：
// { data: ArrayBuffer, filename: string, software: 'a' | 'e' | 'm' | 'r' }
```

| 接口 | 约定 |
| --- | --- |
| `source` | 普通录像字节及格式；组件自己解析和释放 WASM 对象。更换文件时替换整个对象，不原地修改字节；传 null 清空。 |
| `loading` / `errorMessage` | 调用方的文件读取或站内请求状态；解析错误由组件显示。 |
| `title` / `filename` | 可选分析区域的可访问名称和导出文件名前缀；不显示顶部标题，区域名称默认采用本地化的“录像分析”，导出默认采用 source.filename。 |
| `v-model:config` | 配置由调用方保存；未提供时每个实例独立创建默认设置，不读 localStorage。 |
| `v-model:probabilityColorScheme` | 必须提供概率配色；站内包装页绑定原有共享配色，其他入口自行保存。 |
| `v-model:exporting` | 导出期间为 true，调用方据此禁止更换文件或离开路由。组件卸载时中止导出。 |
| `#info` | 宽容器与计数器共享面板，窄容器置顶；未传 slot 时不保留空区域。 |

每个实例持有独立解析对象、播放时钟、进度、区间、关键帧和采样数据。替换源重置录像状态；布局切换不重新解析。导出使用独立解析副本，不推进可见录像。

计数器及自定义事件支持逐事件 `pluck`。加载每个源时，在普通分析之后执行一次 `analyse_for_features(['pluck'])`，从事件快照读取并复用结果；图层更新不触发重新分析，独立视频导出解析对象不计算该特征。默认自定义事件为持续事件 `left`、`right` 和脉冲事件 `pluck`（表达式 `d(pluck)`），已有保存的事件列表不自动覆盖。

默认计数器为 `Bvs`、`Ces`、`Mov`，均连续采样、显示格式 `.3f`，用 `d(..., 1000)` 计算差分速率；`Mov` 再除以 16。Plot 1 包含 `Bvs` 和 `Ces`，Plot 2 包含 `Mov`。不再默认提供小写 `bvs`，已保存配置不覆盖。完整公式见[表达式参考](../../../../vitepress_doc/zh/guide/replay-expressions.md#默认计数器)。

鼠标轨迹默认不显示按键 marker；`lc`、`lr`、`rc`、`rr` 均默认禁用，样式保留库默认值，可在轨迹设置中分别开启。已有保存的开关和样式不覆盖，页面与视频导出使用相同设置。

布局设置位于棋盘右下角、格子大小控件上方。单个布局按钮点击后打开交互式 tooltip，内含“自动”和四种预设的下拉框；选择后关闭，支持 Escape 关闭。加载或报错期间仍可切换布局，配置继续由 `v-model:config` 保存。

时间轴事件行移除 key 的原生 title，整个事件轴共用一个 Tippy，与棋盘复用 `useEventTooltip` 和 `EventTooltipContent`：脉冲点显示时间与表达式原值（布尔结果仅显示时间），持续段显示完整起止时间与持续时间，不使用时间窗裁剪后的端点。两处均跟随悬停位置、只读取已有采样；离开事件、缩放/滚动、更新数据或编辑设置时隐藏时间轴提示。

自定义事件的“棋盘标记大小”仅影响棋盘图层；时间轴脉冲标记固定为 8px，形状、颜色和不透明度仍跟随事件设置。

棋盘自定义事件图层在新配置中默认开启并选中 `pluck`，已有保存的图层开关和选择不覆盖。全棋盘共用一个 Tippy，悬停在事件标记或轨迹时更新内容：脉冲事件显示时间和原值（布尔结果不显示值），持续事件显示完整开始、结束和持续时间，即使轨迹按当前时间裁剪。提示只读取已采样数据，不重复分析或求值；离开事件、取消选择或移除事件时隐藏。

组件不直接请求站内 API、导入路由或持有持久化配置单例，也不复用弹窗 VideoPlayer 的播放状态或组件实现；站内包装只共享明确提供的概率配色。项目 CSS、Vue I18n、基础控件、帮助链接、通知及剪贴板 helper 继续共用；后两者使用轻量 `store/local.ts`。离线构建和部署见 [local-analyzer/README.md](../../../local-analyzer/README.md)，版本变更见 [CHANGELOG](../../../local-analyzer/CHANGELOG.md)。

## 技术边界

- `useReplayPosition` 是可见录像的唯一定位入口，关键帧保留“先时间、后索引、前置局面”的 workaround；上游同步接口修复前，不在图层、计数器或 plot 中另行定位。
- `usePreparedAnalysis` 只根据对应配置、原生事件和时长更新缓存。无关图层设置使用原地修改，保留 VueUse `toRefs(..., { replaceRef: false })`，避免重新采样。
- `pluck` 随录像加载通过 `analyse_for_features(['pluck'])` 分析一次，按库的逐事件返回值采样；不假定未完成录像使用固定失败值，也不把特殊值（如 `NaN`、无穷或 `Number.MAX_VALUE`）归零或替换。读取事件快照和参数后必须释放 WASM 包装对象，不遍历修改页面索引来提取字段。
- `counterDifference.ts` 适配 `expr-eval@2.0.2` 的内部 `Expression.tokens` 和 `IEXPREVAL` 指令，以保留差分参数及条件分支的惰性求值；其他运算仍交给原库，不另写表达式解析器或使用 eval。公共自定义函数会先求值参数，不能直接替代此适配；升级依赖时复查模块并运行差分测试，若上游提供公开接口则优先替换。[求值源码](https://github.com/silentmatt/expr-eval/blob/v2.0.2/src/evaluate.js)、[Expression 源码](https://github.com/silentmatt/expr-eval/blob/v2.0.2/src/expression.js)。字段、步长及采样语义只在中英文表达式参考中维护。
- 棋盘绘制使用 minesweeper-board 的公开组件和独立 render，时间轴使用 vue3-plots；通用能力缺口先请求上游，棋盘自定义事件的原生 SVG 是已确认的独立图层。

## 视频导出

`createExportVideo` 从原始字节创建独立解析副本，不重新请求或推进页面；`boardExportFrame` 将背景、全局、已打开、概率、轨迹、光标合成到裁剪后的编码 Canvas。棋盘事件 SVG 不参与导出，不使用 DOM 截图或 Worker 并行。

Mediabunny/WebCodecs 按冻结的实际尺寸、区间、倍率、格式、帧率和质量有序编码，保留背压及取消检查。硬件候选探测失败时回退普通编码；硬件偏好不保证实际使用 GPU 或提速。帧消费后 release，完成/失败/取消后 destroy 渲染器并释放解析副本，再恢复页面状态；取消不下载不完整成品。BufferTarget 会保留成品数据，不能据此承诺长录像的内存上限。

单元测试覆盖数据及资源生命周期，Cypress 覆盖真实绘制和成品解码；命令由用户运行，静态检查不代替浏览器验证。GIF、多个编码器分段拼接及更多轨迹线型不在当前实现范围。

离线入口将 `#info` 内容换成选择本地录像文件的控件，读取字节后更新 `source`；选择控件沿用 slot 的宽窄容器布局，并在 `exporting` 为 true 时禁用。分析器其余区域及功能直接复用。在 `front_end` 执行 `npm.cmd run build:offline`，生成 `OpenMinesweeperVideoAnalyzer-${version}.zip`，独立版本由 `local-analyzer/version.json` 提供。

站内包装页默认通过 info slot 提供四行网站信息：录像 ID/上传时间、PlayerName/可选比赛 ID、该录像的各榜名次、文件名；右侧独立按钮列提供 StrangeDust Analyzer 链接和离线包下载图标。网站信息请求、PlayerName、比赛、外部分析及下载链接均留在包装页目录，不进入公共组件；信息加载失败不阻塞文件解析与播放或离线包下载。

单元测试：`npx.cmd vitest run src/components/VideoAnalyzer src/views/VideoAnalyzerView`。Cypress 由用户运行：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/VideoAnalyzer/AnalyzerLayoutControl.cy.ts,src/components/VideoAnalyzer/App.cy.ts,src/components/VideoAnalyzer/BoardPanel.cy.ts,src/components/VideoAnalyzer/VideoExport.cy.ts,src/views/VideoAnalyzerView/App.cy.ts,src/views/VideoAnalyzerView/WebsiteReplayInfo.cy.ts"
```
