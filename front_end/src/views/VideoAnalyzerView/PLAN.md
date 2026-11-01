# VideoAnalyzer 发布状态与后续事项

当前版本以 [version.json](../../../local-analyzer/version.json) 为准。版本内容统一见 [CHANGELOG](../../../local-analyzer/CHANGELOG.md)，不在本文件维护进度日志、历史测试计数或重复验收清单。

## 文档与代码入口

| 内容 | 位置 |
| --- | --- |
| 公共组件、接口和技术边界 | [components/VideoAnalyzer](../../components/VideoAnalyzer/README.md) |
| 站内包装与信息 slot | 本目录的 App.vue、WebsiteReplayInfo.vue、useSiteReplaySource.ts、useSiteReplayInfo.ts |
| 本地文件入口 | src/views/LocalVideoAnalyzerView、local-analyzer/main.ts |
| 离线构建、资源和部署 | [local-analyzer/README.md](../../../local-analyzer/README.md) |
| 独立版本与发布约束 | [VERSIONING.md](../../../local-analyzer/VERSIONING.md) |
| 表达式、字段、采样和差分 | [中文参考](../../../../vitepress_doc/zh/guide/replay-expressions.md)、[English reference](../../../../vitepress_doc/en/guide/replay-expressions.md) |

## 已实现范围

- 在线录像页与本地文件入口复用同一个 VideoAnalyzer；网站信息与本地文件选择由调用方提供 info slot。宽容器与计数器共享面板，窄容器信息置顶；支持预设布局和拖动分割线。
- 棋盘共享背景，前景按全局、已打开、概率、鼠标轨迹、自定义事件、光标叠加。已打开图层锁定显示，其他图层独立设置；格子大小支持自适应、固定像素及相对比例。
- 棋盘支持鼠标按下反馈：左键按下时压下光标所在格，双键按下时压下周围 3×3 格，旗格不受影响，视频导出保留相同效果。
- 唯一播放时钟和统一录像定位驱动进度条、关键帧、棋盘及光标。支持倍速、播放区间与循环；设置持久化，播放位置、区间和采样数据不持久化。
- 默认计数器为 Bvs、Ces、Mov，默认 Plot 1 包含 Bvs/Ces，Plot 2 包含 Mov。支持连续、按键、局面变化采样，以及表达式差分、导入导出和轨道编辑。
- ms-toollib 提供逐事件 pluck。每个源加载时分析一次，计数器和事件复用快照；默认 pluck 脉冲表达式为 d(pluck)。默认开启棋盘事件图层并选中 pluck，鼠标轨迹的按键 marker 默认关闭。
- 时间轴与棋盘各共用一个 Tippy，采用相同内容及悬停规则：脉冲显示时间与原值、布尔值省略；持续事件显示完整起止时间和时长。事件轴无原生 title，标记固定 8px，设置中的标记大小只影响棋盘。
- 视频导出使用独立解析对象、主线程渲染及 Mediabunny 编码，支持裁剪、倍率、格式、帧率、质量和取消。棋盘自定义事件 SVG 图层不参与导出。
- 离线 ZIP 支持解压后双击 HTML，包含内联资源、中英文帮助、版本、README 和版权声明；网站构建自动生成同版本下载资源。
- 新默认值只补充缺失配置，不覆盖用户保存的开关、事件、计数器或 plot。

## 后续事项

以下不是当前版本的发布阻塞项，未明确要求前不扩展功能。

| 事项 | 边界 |
| --- | --- |
| 网站字段核对 | 网站信息已提供录像 ID/上传时间、玩家/比赛、录像排名、文件名；文件与数据库字段比对暂缓，后续再确认精度、空值及差异通知。 |
| 关键帧同步 | 保留已确认的 workaround：先设置时间，再指定原生事件索引，使用前置局面；上游接口修复后再替换。 |
| 更多轨迹线型 | [上游需求草稿](./MOUSE_TRACE_LINE_STYLE_REQUEST.md) 仍有效，等待公开接口，不绕过依赖绘图。 |
| 更多分析、字段或数据导出 | 尚未确定范围；计数器与自定义事件继续共享字段定义。 |
| GIF、分享及性能优化 | 未接入 GIF 或分段多编码器；后续优化先测量解析、绘制、编码与内存，不预设瓶颈。 |
| 独立离线 artifact | 现有网站部署会生成 ZIP；独立 artifact/Release 工作流按实际发布需要另行安排。 |

## 维护与验证

维护行为和检查命令遵循根目录 [.codex/instructions.md](../../../../.codex/instructions.md)。改动按所属模块维护测试：公共解析、采样、播放、图层和导出测试在组件目录；站内请求、信息和持久化接线测试在本目录。

Vitest、构建与 ZIP 检查证明对应的代码或产物约束，不替代浏览器运行结果。Cypress 和真实断网 file:// 的播放、首次贴图及导出由用户验证；不要将旧检查记录当成本次发布的验证结论。
