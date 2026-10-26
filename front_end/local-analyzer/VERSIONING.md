# Analyzer 版本管理约束

修改公共 VideoAnalyzer 或离线包前必须阅读本文件。版本覆盖公共组件与离线包，独立于网站 tag 和 `front_end/package.json` 的网站版本。

## 唯一版本来源

当前版本只维护在 [version.json](./version.json) 的 `version` 字段，格式为 `MAJOR.MINOR.PATCH`，初始基线为 `0.1.0`。离线网页直接导入该文件，打包脚本将同一份文件放进 ZIP 根目录；禁止在组件、README 或脚本中手写另一份版本号。

网站软件下载弹窗是发布历史展示的例外：[AnalyzerHelper.vue](../src/components/dialogs/AnalyzerHelper.vue) 的 `tableData` 按用户要求硬编码版本、日期及文件名，手动更新，不随 `version.json` 自动变化。它不作为当前构建版本的来源；提供新版本下载后，将实际可下载的条目手动添加到表格，最新版本放在前面，历史链接只在文件仍可下载时保留。

只有用户明确要求升级 Analyzer 版本号时，才修改 `version.json`。功能开发、修复、依赖升级、构建和网站发布均不主动递增版本；不使用网站 tag、commit 次数、日期或整个仓库的改动作为递增依据。ZIP 命名为 `OpenMinesweeperVideoAnalyzer-${version}.zip`；本地生成、网站 assets 中的文件和下载按钮的文件名均从 `version.json` 的版本派生，用户要求更新版本后同步构建网站下载资源。

## 哪些改动需要记录版本影响

更新记录只记录用户可感知的功能、行为、界面、性能和兼容性变化。代码整理、内部重构、保持显示内容不变的本地化 key 调整、测试或开发工具维护等纯开发改动，不写入 `CHANGELOG.md`，必要的实现和用法说明放在开发文档中。

下列改动产生用户可感知的变化时，记录在 `CHANGELOG.md` 的“未发布 / Unreleased”段；未得到用户明确的版本升级指令时，保持当前版本号。

- 公共组件 `src/components/VideoAnalyzer/` 的功能、默认配置、布局、表达式/计数器语义、播放或导出行为发生变化。
- `src/views/LocalVideoAnalyzerView/`、本目录离线入口、离线使用说明/帮助/版权正文，或离线构建及打包逻辑改变交付给用户的内容或行为。
- 共享 CSS、i18n、基础组件、工具或依赖变化，实际影响 Analyzer 或离线包。判断实际影响，不能只按文件目录决定；依赖升级时检查依赖图、功能和许可文件。

仅修改网站其他功能、在线包装页的网站专有信息/链接、后端业务、开发约束、测试或计划记录，且不影响公共 Analyzer 或离线产物时，保持版本不变。单纯重复构建不产生新版本。

## 如何递增

以下规则仅在用户明确要求升级 Analyzer 版本号后执行。

- 新增兼容功能：递增 MINOR，PATCH 归零。
- 修复问题、兼容性的布局/文案/许可修正：递增 PATCH。
- 不兼容的公开接口、保存配置或表达式行为变化：稳定版本递增 MAJOR，MINOR/PATCH 归零；`0.x` 阶段递增 MINOR，并明确说明不兼容行为和迁移方法。

用户要求升级版本时，手动修改版本，并将 [CHANGELOG.md](./CHANGELOG.md) 中本次未发布的变化归入该版本，记录日期、用户可见变化及必要的兼容说明。一次更新包含多个改动时按最高级别递增一次；同一更新后续的 lint/typecheck 修正、测试维护或文档补充合并到该版本，不按对话轮次机械递增。已发布版本的历史记录保留；后续修复先记录为未发布，等待用户决定何时升级版本。

## 更新时必须完成的工作

1. 判断实际影响范围，有用户可感知的变化时更新 `CHANGELOG.md` 的未发布记录；纯开发改动不新增更新条目。仅当用户明确要求升级版本号时修改 `version.json`，其余情况保持当前版本。
2. 同步必要的使用说明及中英文界面文本，保持页面、ZIP 内 `version.json` 和变更记录中的版本一致。
3. 按 [构建与部署说明](./README.md) 在 `front_end` 执行 `npm.cmd run build:offline`，核对 ZIP 的版本文件、页面版本显示及内联资源检查。网站下载内容也需要刷新时使用 `npm.cmd run build:openms`，其 pre hook 会先生成离线包。
4. 按改动维护相关测试。Cypress 命令留给用户，真实断网 `file://` 打开/解析/导出由用户验收；未运行的验证如实注明。lintfix/typecheck 遵循根目录 [.codex/instructions.md](../../.codex/instructions.md) 的跨轮工作流，不为本约束增加等待或额外审批。
5. 源码、版本文件和变更记录交由 Git 管理；生成的 HTML 目录和 ZIP 沿用 `.gitignore`，不提交二进制产物。需要保留历史包时可发布到独立的 `analyzer-vX.Y.Z` Release；创建 tag/Release 或上传产物必须有用户授权，不由普通更新自动执行。
