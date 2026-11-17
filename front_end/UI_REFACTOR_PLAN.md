# 前端 UI 风格渐进重构计划

制定日期：2026-10-03。现状核对与计划更新：2026-11-15。

本计划只列剩余工作与持续适用的约束。已提交或已验收的批次不再列为实施或测试待办，也不再重复其迁移细节；已完成控件的模板、参数与复用约定以 [`src/styles/README.md`](src/styles/README.md) 与代码为准。原有批次编号保留，避免后续交流中混淆。

新增 UI 和业务维护优先遵守[根目录前端规范](../AGENTS.md)。管理员页面只承接必要的功能与主题兼容，不安排专门的精细视觉改版。

## 目标与固定约束

- 面向数据展示与分析，以直角、紧凑布局和清晰对齐为主，优先减少多余间距，不以普遍缩小字号代替密度改善。
- 同时支持浅色与深色主题。主要配色沿用已提取的 Element Plus 基准值，应用代码使用项目 `--ui-*`，不直接读取组件库颜色变量。
- 组件根据自身可用宽度伸缩、换行或内部滚动；少数确需切换布局的组件单独制定策略，不设置全站宽窄屏布局分界。
- 简单布局和展示采用原生 HTML + CSS，复用项目已有基础组件。复杂交互保留现有组件逻辑，主要调整样式。
- vue-tippy 保持现有实现及样式导入方式。PrimeVue 按项目既定决定逐步退出，PrimeIcons 单独保留。
- 禁止全局注册全量 Element Plus 图标；过渡期仅注册实际依赖全局解析的图标，最终不全局注册任何图标。图标选型继续优先 PrimeIcons，其次 Element Plus。
- 每批围绕一个可独立审查、合并和回退的结果，避免与业务逻辑修改、文件搬迁或整页重写混在一起。

## 当前状态与可复用的基础

以下能力已经落地，后续直接复用，不重新建立同类基础设施。

| 基础 | 当前实现与维护入口 |
| --- | --- |
| 主题与参数 | [`theme/`](src/styles/theme/) 提供独立颜色、字号、圆角、过渡和表格参数；[`setup.ts`](src/setup.ts) 为应用与 Cypress 加载主题和共用原生样式，vendors 库适配由使用方按需导入 |
| 全局文字 | [`text.css`](src/styles/text.css) 设置 body 常规文字色、基础字号和换行方式；div / span 默认零 margin、零 padding，span 默认行内居中 |
| 文字语义 | 普通文本可继承默认样式；需要独立常规文字色时使用 `text-regular`，保留字号与状态色修饰类；标题、链接、控件等仍可使用有实际重置作用的 `text` |
| 有色数据单元格 | [`PiecewiseColorScheme`](src/utils/colors.ts) 按背景明暗引用浅色 / 深色模式的默认文字色；透明背景继承父容器颜色。两套来源为 `--ui-text-color-regular-light` / `--ui-text-color-regular-dark` |
| 布局、卡片与操作 | `layout.css`、`cards.css`、`link.css`、`button.css` / `buttons/`；`BaseButton`、`BaseTextButton`、确认/取消按钮、`BaseFileInput` 等已有原生实现 |
| 描述列表 | [`descriptions.css`](src/styles/descriptions.css) 提供 dl / dt / dd 模板，支持边框、跨列和容器宽度适配，无独立 Vue 组件 |
| 展示表格 | [`BaseTable`](src/components/common/BaseTable.vue) 封装原生表格、滚动容器、空状态和插槽；`table.css` 提供行悬停高亮，`table-columns.css` 提供排名、玩家、数值、时间等公共列样式 |
| 表头排序图标与状态 | [`SortIcon`](src/components/common/SortIcon.vue) 按 `aria-sort` 三态统一 PrimeIcons 类名；[`sortState.ts`](src/components/common/sortState.ts) 提供 `SortState`、`sortState(order, active)` 与 `nextSortOrder(order, active, clearedOrder)`，由 `<th :aria-sort>`、`SortIcon :state` 和表头按钮共用。根元素仍为 `<i>`，支持父级 `class` 合并，供 BaseTable 调用方复用，不接管排序状态或请求；`aria-sort` 仍由列头维护，字段写入、分页重置和后端请求仍由调用方负责；`clearedOrder` 传 `-1` 时可承接仅升 / 降两态切换的表 |
| 保留表格的视觉 | `theme/tables.css` 为 BaseTable、ElTable、PrimeVue DataTable 提供统一参数；`vendors/element-plus-table.css`、`primevue-table.css`、`primevue-table-controls.css` 已接入 |
| Element Plus 按钮兼容 | `vendors/element-plus.css` 提供直角覆盖；应用模板中 ElButton 已归零，ElLink 仅首页比赛卡片仍有 3 处，不重复安排按钮整体迁移 |
| 图标注册 | [`bootstrap.ts`](src/bootstrap.ts) 显式全局注册剩余的 7 个图标；导航已改用 PrimeIcons；组件测试按挂载链注册，7.2 其余范围仍待迁移 |
| 导航布局 | [`Menu.vue`](src/views/Menu.vue) 提供顶栏 / 侧栏设置、单行顶栏溢出菜单与窄容器抽屉；App.vue 将唯一的页面主体放入其插槽，切换布局保留页面实例 |
| 原生 Checkbox | [`checkbox.css`](src/styles/checkbox.css) 与 [`checkbox-buttons.css`](src/styles/checkbox-buttons.css) 由 setup.ts 为应用与 Cypress 加载；原生 input / label + 共用 class，提供直角、主题、选中、半选、悬停、键盘焦点和禁用样式，支持数组多选与按钮外观，无 BaseCheckbox 组件 |
| 原生 Radio | [`choice-buttons.css`](src/styles/choice-buttons.css) 通过 checkbox-buttons.css 加载，提供 radio 按钮 class，与 Checkbox 复用直角、选中、禁用、焦点和主题外观；原生分组与 v-model，无 BaseRadio |
| 原生 Switch | [`switch.css`](src/styles/switch.css) 由 setup.ts 加载，提供原生 checkbox / label 的直角开关外观、普通 / 小尺寸、主题、悬停、焦点及禁用状态，无 BaseSwitch；录像筛选 nfOnly 使用普通 Checkbox 外观 |
| 原生进度滑块 | [`slider.css`](src/styles/slider.css) 由 setup.ts 加载，提供 12px × 20px 沙漏外形及主题参数，原生 range 与 ElSlider 共用；`vendors/element-plus-slider.css` 由使用方按需导入 |
| 原生 Select | [`select.css`](src/styles/select.css) 由 setup.ts 加载，提供 .base-select / --ui-select-*；普通尺寸 28px / 14px，小尺寸 24px / 12px，直角及深浅主题共用，聚焦仅主色边框且优先于 hover，不叠加描边或阴影；无 BaseSelect 组件 |
| 原生 Listbox | [`BaseListbox.vue`](src/components/common/BaseListbox.vue) 自行加载 [`listbox.css`](src/styles/listbox.css)：原生 table / tbody / tr / td + 可聚焦的 radio / checkbox，单选与多选共用同一组件，整行点击即选中、选中行高亮，支持 `#option` 插槽、禁用与空状态；`table` 用 `width:auto` 按内容自动收紧宽度，弹层不再固定 16rem；搜索、清除与分页重置由调用方负责 |
| 保留选择器的视觉 | `vendors/element-plus-select.css` 汇总多选标签和浮层适配，`primevue-table.css` 汇总分页器 Select 适配，共用 --ui-select-* 参数，均由使用方按需导入 |

当前源码事实，后续批次以此为起点：

- BaseTable 已有 44 个 `.vue` 使用方，覆盖排行榜、个人纪录、软件版本列表、导入队列、上传队列、管理员与数据库页面；[`DatabaseView/VideoView.vue`](src/views/DatabaseView/VideoView.vue) 的录像列表由 [`VideoList/App.vue`](src/components/VideoList/App.vue) 用 BaseTable 渲染，已退出 PrimeVue DataTable，也不再使用 ElTable。
- 应用模板中 ElButton、ElCheckbox、ElRadio、ElSwitch、ElText、ElDivider 已归零；ElCard 仅 [`NormalTournamentQueue.vue`](src/views/HomeView/NormalTournamentQueue.vue) 1 处，ElLink 同文件 3 处；仍有 4 处 ElDescriptions、4 个 ElTable 使用方和 4 处 ElSelect，分别见第 2 节、第 3 节与 4.2 开头。
- 目前的尺寸是后续评审的起点：基础文字 14px，普通原生按钮内边距 4px × 8px、行高 1.4；表格单元格内边距 4px × 8px、行高 1.4；普通卡片内边距 10px。这些现值已生效，后续按组件类别调整，不再安排“先抄参数但不接入运行时”的步骤。

## 剩余工作与建议顺序

| 批次 | 工作 | 范围与边界 |
| --- | --- | --- |
| 2 | 剩余描述布局 | 4 个管理员 / GSCAdmin 文件共 4 处 ElDescriptions，随维护处理 |
| 3 | 剩余表格核对 | 其余 4 个 ElTable 根据实际排序、编辑等依赖决定是否保留 |
| 7 | 图标注册迁移 | 剩余 7.2：取消 bootstrap.ts 的 7 个全局注册，同步清理 Cypress 注入与 ESLint 豁免 |
| 4 | 其他控件换肤与尺寸细化 | 4.2.5 剩余 Slider、4.2.6 输入与表单、4.2.7 Tabs、4.2.8 弹窗通知与加载，继续分批推进 |
| 5 | PrimeVue 退出 | 5.0 独立分页器与 5.1 VideoList 原生表格已实现；5.2 已细化为准备、外围控件、逐表迁移、测试与最终清理五段，按表推进 |
| 6 | 局部收尾 | 随每批删除失效导入、重复样式和已无使用方的兼容项，更新本计划 |

4.2.5 的不透明度原生迁移及剩余轨道、提示样式，以及图标 7.2 仍可独立推进；首页比赛卡片和 PrimeVue 全部退出不作为前置条件。

### 2. 剩余描述布局

当前 4 处 ElDescriptions 位于 4 个管理员文件：

- 管理员区域 4 处：`components/GSCAdmin/GeneralInfo.vue`、`views/StaffView/Task.vue`、`VideoModel.vue`、`WeeklyTournament.vue`，随维护迁移；保留动态循环、v-loading 和条件显示。

这 4 个文件目前不在 `eslint.config.js` 的两组 ElDescriptions 禁止清单内，迁移后无需再调整规则例外。后续直接复用模板，按实际列数与跨列需求完善局部 CSS；不复制 ElDescriptions 的完整 API，也不将子控件的交互重写纳入布局迁移。

### 3. 剩余展示表格

BaseTable 的迁移边界保持如下：

- 单元格可包含玩家链接、录像预览、下载、按钮和其他独立操作。
- 页面已有的后端排序状态与请求，可由原生表头按钮配合表头插槽承接；后端分页本身不构成保留 ElTable 的理由。
- 简单行点击可由调用方绑定 `tr`，调用方负责键盘触发及独立单元格操作的事件冒泡。
- BaseTable 不新增内部排序、筛选、选择、展开、编辑、分页或递归列注册体系。分组表头直接使用原生 rowspan / colspan。

当前仍有 4 个 ElTable 使用方，都依赖组件库内部排序，当前均无固定列、选择列或展开列：

| 使用方 | 当前判断 |
| --- | --- |
| [`widgets/IdentifierManager.vue`](src/components/widgets/IdentifierManager.vue) | 使用内部排序及单元格内编辑输入，暂留 |
| [`gsc/AllSummary.vue`](src/views/TournamentView/gsc/AllSummary.vue) | 使用内部客户端排序及嵌套表头，暂留 |
| [`weekly/AllSummary.vue`](src/views/TournamentView/weekly/AllSummary.vue) | 使用内部排序及自定义比较函数、嵌套表头，暂留 |
| [`TournamentList.vue`](src/views/TournamentView/TournamentList.vue) | 使用默认排序和可排序列，暂留；保留原因包含排序，简单行点击本身不是障碍 |

`DatabaseView/VideoView.vue` 已改为查询构建器加 `VideoList`（BaseTable 原生表格）渲染，纳入第 5 节，不再属于 ElTable 迁移范围。其余表格继续使用已统一的视觉样式，不在本批顺带重写内部排序或编辑逻辑。未来按实际使用能力重新评估，而不以表格名称或是否包含按钮作决定。

### 7. 剩余图标注册迁移

应用全局注册已收缩为 `bootstrap.ts` 中的 7 个图标；`main.ts` 只负责能力检测并动态加载 bootstrap，不注册组件。本节只保留 7.2 所需的依赖清单与迁移安排，最终应用与组件测试都不全局注册任何图标。继续保留组件库内部自行导入的图标，不要求移除 `@element-plus/icons-vue` 依赖，也不将 PrimeIcons 的 CSS 类用法视为 Vue 全局组件注册。

当前入口及依赖已核对：

- [`bootstrap.ts`](src/bootstrap.ts) 显式导入并注册 ArrowLeft、ArrowRight、Key、Lock、Message、QuestionFilled、User 共 7 个图标。
- [`Menu.cy.ts`](src/views/Menu.cy.ts) 仅注册登录、注册及找回密码渲染链需要的 Key、Lock、Message、User，共 4 个图标；不再为导航注入图标。
- prefix-icon 等字符串 props 仍需逐项检查，不能只搜索图标标签。
- 已核对当前安装包：ElMenu 子菜单箭头直接导入 `ArrowDown` / `ArrowRight`；ElFormItem 相关状态图标由 ElInput 的校验状态映射承接，加载、成功、失败及密码显隐图标已在库内部导入。这些内部使用本身不要求项目全局注册；`prefix-icon="User"` 等项目传入的字符串仍需全局解析。

7.2 需要逐模块消除的全局依赖如下，去重后仍注册 7 个，其中 5 个有源码使用点；历史注释与 ESLint ignorePatterns 不作为实际使用依据：

| 调用来源 | 图标 |
| --- | --- |
| `Login/LoginForm.vue`、`Login/RegisterForm.vue`、`formItems/EmailFormItem.vue`、`EmailCodeBlock.vue`、`PasswordConfirmBlock.vue` 的输入前缀，共 5 个文件、9 处；找回密码表单复用后面三个组件 | User、Lock、Key、Message |
| [`widgets/UserArbiterCSV.vue`](src/components/widgets/UserArbiterCSV.vue) 的 2 处裸标签 | QuestionFilled |
| 仅剩 bootstrap.ts 注册，应用源码已无调用点 | ArrowLeft、ArrowRight |

`visualization/ColorSchemeSetting.vue` 已改用 PrimeIcons 的 CSS 类，不再依赖 Element Plus 图标裸标签；ArrowLeft / ArrowRight 的注册与 `NativePlayer.cy.ts` 注入属于残留，随 7.2 一并清除。

7.2 需要同步移除的测试注册如下：

| 测试 | 注册图标 |
| --- | --- |
| `views/Menu.cy.ts` | 登录、注册、找回密码弹窗需要的 Key、Lock、Message、User，共 4 个 |
| `Login/LoginForm.cy.ts` / `Login/RegisterForm.cy.ts` | Key、Lock、User / Key、Lock、Message、User |
| `formItems/EmailCodeBlock.cy.ts` / `PasswordConfirmBlock.cy.ts` | Key / Lock |
| `VideoPlayer/NativePlayer.cy.ts` / `views/UserView/UserVideoView.cy.ts` | ArrowLeft、ArrowRight（残留）/ QuestionFilled |

`eslint.config.js` 的 `vue/no-undef-components` 豁免目前是 ArrowLeft、ArrowRight、Check、QuestionFilled 与 `router-view`；Check 已无使用，`router-view` 需保留。

#### 7.2 后续目标：不全局注册任何图标

剩余图标按表单、裸标签分别迁移。优先复用现有 BaseIcon / PrimeIcons；需要 Element Plus 图标时在使用方按名称局部导入，图标 props 改为显式组件绑定，消除全局名称解析。只改变图标依赖，保留尺寸、提示、语义与业务事件。

每完成一个模块，移除对应全局注册及不再需要的测试注册、ESLint 图标名称豁免。字符串图标解析可能没有未解析组件警告，需实际确认图标存在及布局未退化。最后删除应用的图标注册映射与注册循环，组件测试也不再用 `global.components` 注入图标；以源码检查及实际渲染验收确认全局图标注册归零。

### 4. 简单选择控件迁移与复杂组件换肤

本阶段继续小批推进，每类先选择代表实例验收，再推广。4.2.2 曾用于导航重做，不复用其编号；4.2.5 的沙漏滑块外形已落地，其余工作及后续批次尚未实施。仍保留的 ElSelect 调用点为 `UserVideoView.vue` 的模式多选、`GSCAdmin/HistoryVideos.vue` 的录像标识多选、`StaffView/Logs.vue` 的文件搜索和 `StaffView/Medal.vue` 的勋章搜索，分页器内部选择器也保留；它们共用已落地的 --ui-select-* 参数，适配由使用方按需导入。

| 子批次 | 当前范围 | 实施边界 |
| --- | --- | --- |
| 4.2.5 Slider | 3 个文件、3 处 ElSlider；与 Analyzer 原生进度滑块共用的沙漏外形已由 slider.css 提供 | 简单不透明度单独迁移；双滑块及播放器拖动保留组件交互，继续细化轨道和提示样式 |
| 4.2.6 输入与表单 | ElInput 为 17 个文件、33 处，ElInputNumber 为 17 个文件、27 处；另有 5 处 ElForm、19 处 ElFormItem | 先盘点能力和校验依赖，再以登录/注册为换肤试点；不批量替换表单和数值处理 |
| 4.2.7 Tabs | 11 个业务文件、12 处 ElTabs；另有 1 个测试包装组件 | 先验收已有水平换行与逐项选中指示，再细化高度、间距、边框；保留纵向布局和路由状态 |
| 4.2.8 弹窗、通知与加载 | 20 处 ElDialog、2 处 ElDrawer，以及通知和加载调用 | 以 BaseOverlay、登录弹窗、Notifications 为代表，逐类调整内部间距、边角与浮层 |

以上数量按 src 下 Vue 模板声明统计，循环产生的实例不重复计数，组件库内部调用不计入。Radio 和 Switch 优先复用原生表单行为，不新增 BaseRadio / BaseSwitch 状态层；输入与表单是否原生迁移，以逐项盘点结果为准。

按实际需要提取控件高度、间距、行高等项目参数，同时覆盖正常、悬停、焦点、禁用、加载、错误和空状态。不要只将所有控件切为 `small`，也不要直接将所有字号或全局圆角统一缩小来代替逐类检查。

保留主题切换机制。下拉框、弹窗和通知可能挂载到 body，使用组件公开的浮层 class / 样式接口接入，不能只依赖业务页面的 scoped CSS。现有 App.vue 中的浮层层级修复继续保留，确需迁移时单独验证。

#### 4.2.5 Slider：剩余迁移与样式

三处 ElSlider 及 Analyzer 原生进度滑块复用 `slider.css` 的尺寸、polygon 与主题参数；ElSlider 适配由使用方按需导入，原生 range 的 WebKit / Firefox thumb 使用相同参数。入口和维护方式见[样式 README](src/styles/README.md)。Analyzer 的外观变化保留在未发布更新记录中，不自行递增版本号。

以下工作仍未实施：

1. MarkerSetting.vue 的 opacity 使用范围 0～1、步长 0.05，单独评估并迁移为原生 input[type=range] + CSS，复用已落地的沙漏参数，保持数值模型和即时预览；不连带调整半径、描边数值框。
2. RangeSlider.vue 保留双滑块与两个数值框的联动，保持上下界、范围约束及 change 契约，继续细化轨道和提示样式。
3. VideoPlayer/ProgressBar.vue 保留拖动定位、暂停/恢复、毫秒步长与时间提示，单独细化轨道和提示样式，不与播放逻辑维护混在一批。

Slider 使用方涉及公共播放器；实施前检查 Analyzer 与离线入口的实际依赖，按版本管理约束记录用户可见影响，不自行递增版本号。

#### 4.2.6 输入与表单：先核对能力再换肤（尚未实施）

先区分普通文本、密码显示、字数提示、textarea、前后缀、校验触发，以及数值框的 min / max、步长、精度、清空值和提交时机。项目已有 common/InputNumber.vue，优先核对它的能力与现有 ElInputNumber 的差异，不再建立重复的数值输入层，也不假定两者可以直接互换。

先以登录/注册为独立试点，保留 ElForm / ElFormItem、现有校验规则、错误状态和输入处理，仅统一输入高度、内边距、直角、文字/背景/边框及焦点反馈，再推广到 EditProfile 等页面。普通 / 小尺寸优先与已落地的 Select 参数协调，textarea 按内容与 rows 设置，不统一压成单行高度；错误信息和交互图标不能被裁切。

数值框另成小批，保留格式化、空值、范围、键盘和 blur / change 语义；管理员页面随实际维护处理。简单输入的原生迁移按调用点决定，不以 ElInput 导入归零为验收目标；前缀图标取消全局注册仍属于 7.2，不混入换肤试点。

#### 4.2.7 Tabs：先验收已有实现（尚未实施）

水平标签换行和逐项选中指示已由 element-plus-tabs.less 提供，本批先核对首页及一个路由驱动页面的多行标签、长文本、方向键切换和选中指示；纵向标签保持原样。确认已有实现后，再通过项目参数调整高度、内边距和内容间距，每次提供独立视觉验收，不重新实现标签注册、面板生命周期或路由状态。

#### 4.2.8 弹窗、通知与加载：逐类推进（尚未实施）

依次以 BaseOverlay、登录弹窗、Notifications 和 v-loading 的代表调用为试点，分别验证关闭方式、焦点返回、滚动锁定、遮罩、加载状态、错误内容与层级。先改内容和操作区域的间距及边角，不重写浮层状态管理。导航抽屉已有验收结果，保留其布局和行为，仅核对共用适配的兼容性。

以上各批的新参数继续使用项目 --ui-*；vendors 样式由实际使用方按需导入，不回到 setup.ts 全局加载。样式文件仍受 100 个非空行限制；代码变更完成后按现有跨轮流程执行检查，Cypress 命令随各批实际改动提供。

### 5. PrimeVue 退出

不新增 PrimeVue 使用范围。当前依赖仍包含以下内容，表内分页器之外的实际行为也必须保留：

| 依赖 | 当前使用方 |
| --- | --- |
| DataTable / Column | `views/StaffView/Task.vue`，仅剩 1 个表格入口；VideoList、AccountLink、VideoImportQueue、MSGamesVideoImportQueue、IdentifierView 与 VideoUpload/Table 已退出 |
| Listbox | 5.2.1.1 规则已重订：3 个文件共 6 个实例统一改为原生 table 的 `BaseListbox`，纵向按钮组不再是迁移目标，无剩余使用方；VideoList 的 4 个列筛选此前已改为原生控件 |
| Toolbar | 仅 `views/StaffView/Task.vue` 的 1 处；账号关联旧 Toolbar 已随卡片删除 |
| InputText | 5.2.1.2 已把 2 处换成原生 `<input>`，无剩余使用方 |
| 注册、主题与类型 | [`bootstrap.ts`](src/bootstrap.ts) 中的 PrimeVue / Aura preset，`@primevue/core/api`、DataTable 事件类型及仍使用 PrimeVue 表格的 Cypress 测试注册；VideoList 调用链已清理 |

#### 5.0 独立原生分页器（已实现，接口供 5.1 复用）

已新增 [`components/common/BasePagination.vue`](src/components/common/BasePagination.vue)，用原生 HTML / CSS 与已有 BaseButton 实现，不依赖 PrimeVue、Element Plus 或 VideoAbstract；区间计算集中在 [`components/common/pagination.ts`](src/components/common/pagination.ts)，样式见 `styles/pagination.css`。已有页面未在本批切换，现有 DataTable 分页器保持原样。以下保留公开接口作为 5.1 的接入契约。

分页器只管理分页控件与记录索引区间，接收总记录数，不接收或切片数据、不排序、不筛选、不请求 API、不维护路由或持久化状态。本地分页与后端分页均由调用方承接，BaseTable 保持原有展示职责。界面与公开接口均使用从 1 开始、两端包含的记录索引；索引表示当前结果集合中的位置，不是录像 ID。

公开接口与行为约定：

| 接口 | 约定 |
| --- | --- |
| `v-model:current-start` | 当前区间的第一个记录索引，默认 1；其值不是页码，允许任意合法起始索引。VideoList 的零基 `first = currentStart - 1`，不按页容量取整 |
| `v-model:page-size` | 正整数，默认 25；用户切换页容量时同步将起始索引重置为 1 |
| `total` | 非负总记录数；本地分页传过滤后数量，后端分页传服务端总数 |
| `page-size-options` | 默认 `[5, 10, 25, 50, 100]`，允许调用方配置；当前有效页容量不在选项中时仍能正确显示 |
| `disabled` | 禁止分页操作，供加载期或业务限制使用，保持控件尺寸与位置 |
| `change` | 一次有效用户操作只发出一次 `{ start, end }`，两者均为从 1 开始且包含端点的记录索引；非空时 `start = currentStart`、`end = Math.min(start + pageSize - 1, total)`，空结果为 `{ start: 0, end: 0 }`。调用方不与模型监听重复绑定同一请求 |

- 提供上一页、下一页、有限数量的区间按钮与省略号、页容量、按起始索引跳转和当前记录区间 / 总数；上一页 / 下一页并排放在所有区间按钮之前，首段与末段区间按钮始终显示，承担跳到开头 / 结尾，不另设首页 / 末页按钮。常规按钮按页容量分段，显示 `1-25`、`26-50` 等索引范围，末段截断到总数；点击后将起始索引设为该段首个索引。总数很大时不创建全部区间按钮。
- 跳转输入的是目标区间第一个记录索引，不要求对齐常规分段。例如页容量 25、总数至少 37 时输入 13，模型值为 13，显示 `13-37`，`change` 发出 `{ start: 13, end: 37 }`。非对齐区间也需明确显示为当前选中区间，不把它标记成 `1-25` 或悄悄取整。
- 上一页 / 下一页以当前起始索引减 / 加页容量，向前越界时取 1，当前区间已包含最后一条记录时禁用下一页；已在起点时禁用上一页。跳到开头 / 结尾改为点击首段 / 末段区间按钮。
- 零记录时模型保留 1 作为起始索引哨兵，实际区间为 `0-0`，区间 / 总数显示 `0-0 / 0`，翻页与跳转禁用；调用方按空结果处理，不将 0 转成数组负索引。
- 总数缩小或外部模型越界时，将非空结果的起始索引约束到 `[1, total]` 并按需同步模型，保持任意合法起点，不对齐常规分段，不发出用户 `change`；外部模型同步不重复回发相同值。外部总数 / 页容量联动更新时以最终有效状态计算，避免中间状态造成重复通知。
- 跳转输入允许编辑中的空值，提交时处理非整数、非法值和越界值；Enter 与失焦不重复提交，跳到当前起始索引不发出无效事件。
- 采用带可访问名称的 `nav`、原生按钮 / select / input，当前区间使用 `aria-current="page"`，跳转输入明确标注“起始索引”；复用项目按钮、Select、文字和主题参数，支持焦点、禁用、深浅主题与紧凑布局。按组件自身宽度线性估算区间按钮数量：先扣除导航按钮、设置区与省略号的估算占用 180px，再按每 100px 增加一个区间预算，限制在 1~17，覆盖 1920×1080 及更宽屏幕；始终保留首段 / 当前段 / 末段与省略号，仍允许控件组换行，不引入全站视口断点。

验证范围包括零 / 单段、多段和大总数、首末段、页容量重置、常规区间按钮、任意起始索引跳转及连续翻页、末端截断、总数变化、外部模型更新、`start` / `end` 端点与事件次数，由 `pagination.test.ts` 覆盖计算边界、`BasePagination.cy.ts` 覆盖实际交互，避免两套测试重复验证全部用例。Cypress 由用户运行。样式按实际需要拆分，每个文件不超过 100 个非空行。

5.1 已直接复用该组件，VideoList 的 DataTable 分页器已随之退出；数据库查询页仍保留页面自有分页。

#### 5.1 VideoList：VideoAbstract 专用原生表格（已实现）

[`VideoList/App.vue`](src/components/VideoList/App.vue) 已弃用 PrimeVue DataTable，改用 BaseTable + 原生 HTML / CSS，保留筛选、单字段排序、分页和现有单元格操作。实现分为 [`videoListData.ts`](src/components/VideoList/videoListData.ts) 的纯数据逻辑、[`VideoListCell.vue`](src/components/VideoList/VideoListCell.vue) 的单元格、[`VideoListFilter.vue`](src/components/VideoList/VideoListFilter.vue) 的列头筛选与 `styles/videoList.css`。仅面向 `VideoAbstract`，按 `ColumnChoice` 定义固定列及其渲染、排序能力；不建设通用表格引擎或递归列注册体系，不引入其他表格库。

当前 5 个直接调用方为首页 `NewestQueue.vue`、`ReviewQueue.vue`，个人主页 `UserVideoView.vue`，比赛 `common/PersonalView.vue` 与数据库 `DatabaseView/VideoView.vue`。VideoList 当前没有行选择、展开、编辑或固定列，这些能力不纳入本轮范围；其他 PrimeVue 表格保持独立迁移。

职责与兼容边界：

- BaseTable 继续只提供原生表格、滚动容器、空状态与公共样式；筛选、排序、分页状态及数据处理放在 VideoList 内，不向 BaseTable 增加交互引擎。
- 保留 `videos`、`columns`、`paginator`、`paginatorRows`、`sortable`、`externalFiltering`，以及 `first`、`rows`、`sortField`、`sortOrder`、`filters` 的双向绑定和 `rowActions` 插槽；新增 `displayOnly` 供数据库查询页使用，新增 `includeLocal` 让外部筛选的调用方声明本地录像是否存在。保留默认排序；`sortable` 控制用户能否切换排序，不能顺带取消既有默认顺序。
- 内部筛选仍覆盖状态、软件、等级与模式，列头按钮 + Tippy 弹层内复用 `SoftwareFilter` / `VideoStateFilter`，等级与模式均使用按钮组（等级单选、模式多选），选项数量少，弹层不再提供重置按钮；保留单选 / 多选、清空与空数组的实际语义，等级额外支持自定义等级，状态筛选在存在本地录像时提供 `l`。个人主页与 VideoList 共用同一份 `VideoListFilters` 与 `filterVideos`，不再维护页面专用的空数组语义。列头图标用 `pi-filter` / `pi-filter-fill` 区分未生效与生效的筛选器，`displayOnly` 关闭筛选时显示 `pi-filter-slash`。
- 数据处理顺序为筛选 → 排序 → 分页。基于原始数值、日期及 `VideoAbstract` getter 排序，显示继续使用现有格式化逻辑；不按显示文字排序，不原地修改传入数组。非有限值、缺失 / 无效日期不论升降序恒排末尾，同值记录保持输入顺序。
- 分页复用 5.0 的 BasePagination，`currentStart = first + 1`、`pageSize = rows`；区间显示为 `1-25` 等形式，允许任意起点。非空区间 `{ start, end }` 对应 `slice(start - 1, end)`，因为公开 `end` 是包含端点的索引，恰好对应数组切片的排除上界。保留首末页、上一页 / 下一页、每页条数 `[5, 10, 25, 50, 100]`、按起始索引跳转及记录数；筛选、用户切换排序或页容量后将 `first` 重置为 0，刷新后起始索引越界时修正，空结果单独处理。
- 保留 `rowKey`，兼容本地 CSV 录像的占位显示与禁止预览、隐藏行操作等行为；保留玩家链接、软件说明浮层、录像预览和 `rowActions` 操作菜单，独立单元格操作不误触整行预览。
- 表头排序采用原生按钮与 `aria-sort`，并通过 `SortIcon`、`sortState` 与 `nextSortOrder` 统一三态图标、状态判定和切换顺序（`pi-sort-amount-down` 表示降序、`pi-sort-amount-down-alt` 表示升序，未排序列使用中性图标 `pi-sort-alt`）：当前排序列用主色高亮并显示当前方向，其余列淡色显示中性图标；清除排序只取消高亮，图标仍按未排序列处理。`aria-sort` 仍绑定在 `<th>` 上，图标组件只消费状态；`nextSortOrder` 只返回下一顺序，字段写入、分页重置和后端请求仍由调用方负责。行预览保留鼠标操作并支持键盘触发；分页、筛选及操作菜单保留焦点、禁用和键盘行为。复用项目主题、公共列样式与 Tippy，支持深浅主题和容器内横向滚动。

`externalFiltering` 只关闭内部筛选计算，列头筛选 UI 仍保留，状态由 `v-model:filters` 交给调用方，且不隐式关闭排序或分页；`displayOnly` 是仅由数据库查询页使用的显式纯展示开关，同时关闭筛选 UI、内部筛选、排序、切片与 BasePagination 渲染。各调用方维持以下分工，避免重复处理：

| 场景 | 页面负责 | VideoList 负责 |
| --- | --- | --- |
| 首页最新 / 待审录像、比赛个人页 | 获取录像与配置展示列 | 内部筛选、分页；按原有配置开放排序切换 |
| 个人主页 | 日期 / BV 范围选择、表格 / 散点切换及共享筛选状态（表格模式由列头弹层修改，散点模式保留页面一排控件） | 对传入结果排序、分页，双向同步状态并渲染列头筛选 UI；分页不影响散点收到的完整筛选结果 |
| 数据库查询页 | 后端查询、筛选、排序和结果分页，以及页面自有的独立分页 UI（`data-cy=page-buttons` / `page-size`） | 传入 `displayOnly`，仅展示页面已切好的 `pageRows`，不重复排序或分页，也不渲染第二套分页器 |

三批均已实施，以下保留拆分依据与仍需用户执行的验证。

##### 5.1.1 提取专用数据处理逻辑（已完成）

[`videoListData.ts`](src/components/VideoList/videoListData.ts) 提取仅服务 VideoAbstract 的筛选、稳定比较、结果切片与固定列配置，索引区间通用计算复用 5.0；`videoListData.test.ts` 覆盖组合筛选与清空、原始数值 / 日期及派生值排序、缺失值、稳定顺序、输入数组不变、筛选结果与任意起始索引切片衔接、本地录像和自定义等级。

##### 5.1.2 切换原生表格与控件（已完成）

VideoList 已接到上述逻辑，改用 BaseTable、BasePagination 与列头 Tippy 弹层；9 个 PrimeVue 列包装已删除，统一由 [`VideoListCell.vue`](src/components/VideoList/VideoListCell.vue) 的单元格内容替代，继续复用 PlayerName、SoftwareIcon、VideoStateIcon、GameLevelIcon 等业务组件。[`App.cy.ts`](src/components/VideoList/App.cy.ts) 覆盖筛选后翻页、排序重置、外部模型更新、行操作、本地录像与纯展示模式；深浅主题与窄容器仍需人工检查。

##### 5.1.3 回归与依赖清理（代码已完成，运行验证待用户）

`UserVideoView.cy.ts`、`VideoView.cy.ts`、`HomeView.cy.ts` 已改用 `[data-cy=video-list-table] table` 等稳定定位并移除不再需要的 PrimeVue 插件注册；E2E 沿用通用 `table:visible` 定位。VideoList 路径的 DataTable / Column / Listbox、筛选类型、列包装、样式导入与测试注册均已删除；仍服务其余表格的适配样式、注册和包依赖继续保留。

待用户执行：Cypress 组件 spec、个人主页 / 数据库查询页 / 首页 / 比赛调用链的 E2E，以及生产构建与产物检查。验证重点为筛选 / 排序 / 翻页不新增录像请求、页码与排序状态双向同步、表格 / 散点切换、预览及独立单元格操作。加载性能收益以构建与测量结果为准，不把局部迁移视为整个项目已退出 PrimeVue。

#### 5.2 其他使用方与最终清理（a / b / c / d / e 已实施，运行验证待用户）

5.2 把 PrimeVue DataTable 使用方按「一表一批」退出；a / b / c / d / e 已实施，运行验证待用户，当前剩 1 个表格，全部退出后才删除依赖。每批独立审查、合并与回退；不新增 PrimeVue 使用范围，不把 [`VideoList/videoListData.ts`](src/components/VideoList/videoListData.ts) 的 VideoAbstract 专用逻辑推广为通用表格引擎，也不预先批量改写尚未轮到的表格。PrimeIcons、5.0 的 BasePagination 与 5.1 的公共基础继续保留；BaseTable 只负责展示，交互状态由各调用方维护。

##### 5.2.0 准备与准入

1. 复核下方的起点事实表并固定 a→f 顺序；注册点现为 4 处（`bootstrap.ts`、3 个 `.cy.ts`），`accountlinks/testUtils.ts` 已随 c 批次、`DatabaseView/IdentifierView.cy.ts` 已随 d 批次、`VideoUpload/Table.cy.ts` 与 `VideoUpload/App.cy.ts` 已随 e 批次移除 PrimeVue 注册，任何使用方的能力发生变化，先更新该表再开始对应批次。
2. `eslint.config.js` 已按文件清单风格禁止新增 `primevue/*` / `@primevue/*` / `@primeuix/*` 导入，现有直接依赖文件按批退出后逐条删除豁免；规则不扩展到 `primeicons`。
3. 固定替代分工：BaseTable 提供 `head` / `default` 插槽、滚动容器与空状态，表头排序按钮、筛选控件、选择 / 展开状态与分页请求均留在调用方；分页统一复用 BasePagination，不新建通用表格组件或递归列注册体系。
4. 固定每批验收清单：保留原有排序（前端 / 后端）、筛选、分页、选择、展开、行操作与请求参数；数据处理顺序为筛选 → 排序 → 分页；筛选或页容量变化后重置起始索引；保留 `data-cy` 定位、键盘与禁用行为；深浅主题与窄容器人工检查。

起点事实与迁移顺序（2026-11-14 核对的迁移起点：6 个 DataTable / Column 使用方、3 个文件共 6 个 Listbox 实例、2 处 InputText、1 处 Toolbar；其中 Listbox、InputText 已分别由 5.2.1.1、5.2.1.2 替换，AccountLink 表格已由 5.2.2-a 替换，VideoImportQueue 表格已由 5.2.2-b 替换，MSGamesVideoImportQueue 表格已由 5.2.2-c 替换，IdentifierView 表格已由 5.2.2-d 替换，VideoUpload/Table 表格已由 5.2.2-e 替换，当前剩 1 个 DataTable / Column 使用方）：

| 批次 | 使用方 | 现有能力 | 迁移重点 |
| --- | --- | --- | --- |
| a | `StaffView/AccountLink.vue` | 5.2.2-a 已改为后端分页 + 固定列交互（见下方契约） | 已退出 PrimeVue DataTable，运行验证待用户；重点验证 BaseTable + BasePagination 与后端分页请求的衔接 |
| b | `accountlinks/VideoImportQueue.vue` | 5.2.2-b 已改为 BaseTable + BasePagination 与本地筛选 / 排序 / 分页 | 已退出 PrimeVue DataTable，运行验证待用户；重点验证筛选 → 稳定排序 → 分页顺序、表头三态排序、筛选后页码重置与单元格预览 / 导入；等级与导入状态两个 BaseListbox 筛选已从表格上方移入各自列头的 Tippy 弹层（触发器 `data-cy=filter-*-trigger`），列头排版参照 VideoList 用原生按钮把列名与 `SortIcon` 编组、图标按 `0.75em` 相对表头字体缩放，表头文本与 `extractTableData()` 键名不变 |
| c | `accountlinks/MSGamesVideoImportQueue.vue` | 5.2.2-c 已改为 BaseTable + BasePagination 与本地筛选 / 排序 / 分页 | 已退出 PrimeVue DataTable，运行验证待用户；数据处理在 `msgamesImportQueueData.ts`，保留表头内分类输入与状态 select、仅 `upload_date` 的两态排序（`-1` ↔ `1`）、默认降序、页容量 `[10,25,50,100]`、筛选 / 排序后起始索引重置与导入 / 重试；局部 `:deep(.p-*)` 覆盖已删除 |
| d | `DatabaseView/IdentifierView.vue` | 5.2.2-d 已改为 BaseTable + BasePagination 与本地筛选 / 排序 / 分页 | 已退出 PrimeVue DataTable，运行验证待用户；数据处理在 `identifierViewData.ts`，保留 `null` 无筛选与空数组筛空的区分、归属多选 + 内置搜索 + 清除按钮的 Tippy 表头弹层、Escape 关闭、`identifier` / `safe` 两列两态排序及默认升序、页容量 `[10,25,50,100]` 默认 25、staff 行菜单与 ElDialog 不动；`:pt` / `:deep(.p-*)` 覆盖与 `primevue-table.css` 导入已删除 |
| e | `VideoUpload/Table.vue` | 5.2.2-e 已改为 BaseTable + BasePagination 与本地筛选 / 排序 / 分页 | 已退出 PrimeVue DataTable，运行验证待用户；数据处理在 `uploadTableData.ts`，保留三字段等值筛选（`status` / `stat.level` / `stat.mode`）、4 列两态排序与 `aria-sort`、页容量 `[5,10,25,50,100]` 默认 25、`filteredData` 与 `selectedRows` 联动及表头半选、跨页全选、Space 键盘行为、展开行描述列表；三组筛选改为对应 `<th>` 内的纯图标 Tippy 触发器（不增加表头文本，不影响 `getTable()` 键名），模式筛选项改用模式代码；表头参照 [`VideoList/App.vue`](src/components/VideoList/App.vue) 与 `styles/videoList.css`，每个 `<th>` 用 `.upload-head` 的 inline-flex（`gap: 2px`）把列名、排序图标与筛选图标排成一组：可排序列把列名与 `SortIcon` 放进同一个原生按钮（列名单独包一层无属性 `<span>`，避免换行空白污染 `getTable()` 键名），筛选触发器是紧随其后的原生图标按钮；按钮用 `font: inherit` / `color: inherit` 跟随表头字体，图标按 `0.75em` 相对缩放、未排序列的排序图标 `opacity: 0.45`，保留 focus-visible 与 hover；首列展开按钮仍用 `.upload-icon-button` 的 `font: inherit` / `color: inherit` 跟随所在行字体；展开列与多选框列由 `<colgroup>` 固定宽度；新增软件 / pLuck / thrp 三列，软件列用 `SoftwareIcon` 图标、无表头文字，位于多选列与状态列之间并固定窄列宽，pLuck 在上传解析时按需执行一次 `analyse_for_features(['pluck'])`；`FilterMatchMode` / `DataTableFilterEvent` / `:deep(.p-*)` 与 `primevue-table.css` 导入已删除 |
| f | `StaffView/Task.vue` | 唯一 lazy 后端排序 / 筛选 / 分页、多选行批量删除、InputText 筛选、Toolbar、失败任务重启 | 排在最后并随管理员任务页维护处理；`@page/@sort/@filter` 改为显式请求函数 |

**a 批次的列交互契约（5.2.2-a 已实施，运行验证待用户）**：迁移前 `GET /api/accountlink/admin/queue` 返回 `AccountLinkQueue` 全量（`id` / `platform` / `identifier` / `userprofile` / `verified`），页面用 `PrDataTable` 做 rows=10 本地分页、4 列前端排序、无筛选。现在按下表实现，不沿用「前端排序 + 本地切片」：

| 列 | 交互 |
| --- | --- |
| 《用户 ID》（表头 `prop.userId`，字段 `userprofile`） | 仅排序，走后端 |
| 《平台》（`platform`） | 仅筛选，选项取自 `AccountLinkPlatform` 全部现有支持的平台（含自动绑定平台），随平台常量维护，不写死列表；页面顶部手动绑定表单的 `manualAccountLinkPlatforms` 只列 6 个手动绑定平台，两者用途不同 |
| 《已验证》（`verified`） | 仅筛选 |
| 《平台 ID》（`identifier`） | 不提供排序、筛选等交互 |

绑定分手动与自动：页面顶部表单只用 `manualAccountLinkPlatforms` 的 6 个手动绑定平台；`AccountLinkQueue.platform` 的取值来自后端 `Platform` 枚举（9 个），因此筛选选项按 `AccountLinkPlatform` 全集维护，不复用表单列表。两者范围不同属于既有设计。

后端分页：`/admin/queue` 按[根目录后端规范](../AGENTS.md)扩展为接收页容量、起始索引 / 页码、`platform` / `verified` 筛选与《用户 ID》排序参数，并返回当前页数据与总数；沿用 Ninja API、`staff_required`、`create_schema` 和 docstring 装饰器说明，权限与参数校验留在 API 层，管理员 API 不加限流。前端把后端 `total` 交给 BasePagination，由 `change` 及筛选 / 排序变化触发重新请求，不再对全量结果本地切片；筛选或排序变化后重置起始索引且不重复发请求，空结果、越界起始索引、请求中的 loading 与禁用态按 5.0 / 5.1 约定处理。两列筛选优先复用 `.base-select` / 原生按钮组，不新增重置按钮。该接口还被 `cypress/e2e/accountlink.cy.ts` 的 intercept 使用，响应结构与 pathname 匹配已同步。两列筛选放在表格上方的紧凑筛选行，表头保持纯文本列名以免污染 E2E 表头断言；用户 ID 列为三态排序（未排序 → 升序 → 降序 → 清除），平台 ID 列无交互；`AccountLink.cy.ts` 新增排序 / 筛选 / 翻页的请求参数断言。

##### 5.2.1.1 Listbox → 原生 table Listbox（规则已重订，运行验证待用户）

原规则把 6 个 Listbox 换成纵向按钮组（`.checkbox-buttons--vertical`）：按钮内容 `width: 100%` 会撑满行宽，弹层只能固定 `16rem` 容器，短选项也留大片空白。规则改为统一使用 [`BaseListbox.vue`](src/components/common/BaseListbox.vue) + [`listbox.css`](src/styles/listbox.css)：原生 `<table>/<tbody>/<tr>/<td>` 呈现选项，`<td>` 内放可聚焦的原生 radio / checkbox 与 `<label>`，整行点击即选中、选中行高亮；`table { width: auto; table-layout: auto; }` 让宽度按内容自动收紧，弹层只保留 `width: fit-content` 与 `max-width`，超过 12rem 由外层滚动容器承接。

1. 组件契约：泛型 `TValue` / `TModel` 让单选（`T | null`）与多选（`T[] | null`）共用同一组件；`options` 为 `{ value, label, disabled? }`，`#option` 插槽可替换选项内容，`emptyText` 提供空状态。单选 radio 由组件内 `useId()` 分组，Tab / 方向键 / Space 全部交给原生 input；根容器单选为 `role=radiogroup`、多选为 `role=group`，不引入自定义 listbox role。组件只负责选项展示与选中值，搜索、清除按钮、筛选值存储与分页重置仍由调用方负责；弹层宽度不再固定。
2. 6 个实例：`VideoUpload/Table.vue` 的 status / stat.level / stat.mode 与 `accountlinks/VideoImportQueue.vue` 的 level / import_status 共 5 个单选改用 `v-model` 或 `:model-value` + `@update:model-value`（VideoImportQueue 的两个已随 b 批次收进对应列头 Tippy 弹层）；`DatabaseView/IdentifierView.vue` 的 ownerKey 多选保留自有 `ownerSearch` / `visibleOwnerOptions` 与 `null` 表示无筛选的语义，`#option` 插槽继续渲染 `PlayerName`，空数组由调用方归约为 `null`。调用方的 `useId()` 组名、`radio-button` / `checkbox-button` 标记与固定宽度弹层样式已删除；公共 `checkbox-buttons.css` / `choice-buttons.css` 保留给原有原生按钮组，`.checkbox-buttons--vertical` 已无使用方，留到 5.2.4 最后清理时再删。
3. 契约不变：保留 `EQUALS / CONTAINS / IN` 的匹配语义、`filters.*` 的 null / 数组 / 字符串值类型、筛选触发时机、清除筛选与 `currentStart=1` 重置；多选的空数组与 null 不合并，`filterIdentifiersByOwner` / `filterUploadTable` 的严格相等语义不变。测试定位改为 `input[data-listbox-value=*]`、`input[aria-label=*]` 的 label 点击与 `input:checked`；新增 `common/BaseListbox.cy.ts` 覆盖单选 / 多选 / 键盘 / 禁用 / 空状态与按内容收紧宽度。

##### 5.2.1.2 InputText → 原生输入（已实施，运行验证待用户）

2 处 `PrInputText` 已换成原生 `<input type="text">`：

1. `StaffView/Task.vue` 的任务路径筛选用 `class="base-select"`，保留 `v-model="filterModel.value"` 和 `@keydown.enter="filterCallback()"` 只在回车提交的行为；`MSGamesVideoImportQueue.vue` 的分类筛选用局部 `.msgames-filter-control`，与同表头的原生 select 共用样式，保留分类 `contains` 匹配语义、筛选后起始索引重置与 `placeholder` / `aria-label`。c 批次已把 `filters.category.value` 改为组件自有的 `filters.category`，`watch(filters)` 将 `currentStart` 重置为 1。
2. `styles/select.css` 增加 `input.base-select { cursor: text; }`，避免原生 select 的手型光标落到文本输入框上；`.base-select` 的直角、主题变量与焦点态不变。
3. `MSGamesVideoImportQueue.vue` 的 `:deep(.p-inputtext)` / `:deep(.p-select)` 直角覆盖与 `vendors/primevue-table.css` 导入已删除；c 批次分页器改用 BasePagination 的 `.base-select`，不再依赖 `vendors/primevue-select.css` 的 `--p-select-border-radius`。两个组件的 `PrInputText` 导入已删除；`Task.cy.ts` 只覆盖 status select，无需改定位，`MSGamesVideoImportQueue.cy.ts` 现用 `[data-cy=filter-category]` 与 `[data-cy=filter-import-status]` 定位。

同一文件先只换控件、不同时重写表格状态；即将进入 5.2.2 的表可合并为一批。`StaffView/Task.vue` 的 PrToolbar 与账号关联卡片按[根目录规范](../AGENTS.md)暂缓，不复制整套 Toolbar API；`VideoUpload/ToolBar.vue` 与 `components/visualization/VideoScatter/Toolbar.vue` 是项目组件，不能仅凭名称列入 PrimeVue 移除清单。

##### 5.2.2 逐表迁移（每表一批，按 a→f）

每批固定执行以下六步，前一批验收通过后再开下一批：

1. 模板换 BaseTable 的 `head` / `default` 插槽，列宽与对齐复用 `table-columns.css`；表内 paginator 换成页面自有 BasePagination，按 `currentStart = first + 1`、`pageSize = rows` 换算，并按各表现值传 `page-size-options`（`[5,10,25,50,100]` 或 `[10,25,50,100]`），不统一回落到默认值；自定义 `paginator-template` / `JumpToPageInput` / `currentPageReportTemplate` 用 BasePagination 的区间按钮、跳转输入与记录数报告承接。
2. 排序改为表头按钮 + `aria-sort`（参照 `VideoList/App.vue`），前端排序提取为纯函数并用 Vitest 覆盖边界；a 改为、f 保留服务端排序，只给契约允许的列挂排序按钮，其余列不新增交互。`Task.vue` 按 `page = Math.floor((currentStart - 1) / pageSize) + 1` 换算请求参数，`page/page_size/status/task_path/sort/reverse` 不变。
3. 删除该文件的 `FilterMatchMode` / `DataTableFilterEvent` 引用，换成自有常量、比较函数与 `filteredValue` 类型；保留默认排序、稳定顺序、缺失值排末尾等既有语义。
4. 选择 / 展开 / 行操作留在调用方：`VideoUpload/Table.vue` 的 checkbox 半选、`#expansion` 描述列表和 `@filter` 后裁剪 `selectedRows`；`Task.vue` 的多选批量删除与请求参数；`IdentifierView.vue` 的 staff 行菜单与 ElDialog 表单；其余表的单元格预览 / 导入 / 重试按钮。
5. 同步删除该文件的 `primevue-table.css` 导入、`primevue/*` 与 `@primevue/core/api` 导入、局部 `--p-*` / `:deep(.p-*)` 覆盖；仍服务其他表格的 vendors 文件不动。
6. 更新第 5 节依赖表与剩余使用方清单，再开始下一表。

##### 5.2.3 测试与验证（随每批同步，Cypress 由用户运行）

1. 删除对应 `.cy.ts` 的 PrimeVue 插件注册，把 `.p-listbox-option` / `.p-paginator-next` / `.p-datatable-*` 等定位改为 `data-cy`；表格文本复用 `cy.getTable` / `cy.extractTableData`，并覆盖 `change` 事件、页码与排序状态双向同步。`VideoImportQueue.cy.ts` 已改用 `[data-cy=saolei-import-table] table` 与列头筛选触发器 `data-cy=filter-*-trigger`，覆盖默认排序、三态排序、等级 / 状态筛选、页容量 / 跳页、筛选后页码重置与单元格导入。`MSGamesVideoImportQueue.cy.ts` 已改用 `[data-cy=msgames-import-table] table`、`[data-cy=msgames-import-pagination]` 与表头控件 `data-cy`，覆盖空状态、两态排序 `aria-sort`、分类 / 状态筛选、首末段 / 页容量 / 跳页、筛选后起始索引重置与一次 `@videos` 请求。`IdentifierView.cy.ts` 已改用 `[data-cy=identifier-table] table`、`[data-cy=identifier-pagination]` 与 `[data-cy=filter-owner-*]` 定位，表格文本统一走 `cy.extractTableData()`；覆盖默认 / 切换排序与两列 `aria-sort`、归属多选与清除、Escape 关闭弹层、页容量 / 跳页、空状态与一次 `@matches` 请求，staff 行菜单与 ElDialog 断言保持不变。`VideoUpload/Table.cy.ts` 与 `VideoUpload/App.cy.ts` 已移除 PrimeVue 插件注册；前者改用 `[data-cy=upload-table] table`、`[data-cy=upload-pagination]` 与 `[data-cy=filter-*]` 定位，覆盖跨页全选、Space 键盘行为、筛选后裁剪已选行、表头半选、页容量 / 跳页、单列排序 `aria-sort`、展开描述列表与空状态，并断言表头为 VideoList 式 inline-flex 分组、图标按表头字体相对缩放、未排序列图标淡色及排序列图标激活；后者保留 `getTable()` 的精确表头键名与单元格文本断言。组件 spec 为 `StaffView/AccountLink.cy.ts`、`StaffView/Task.cy.ts`、`DatabaseView/IdentifierView.cy.ts`、`VideoUpload/Table.cy.ts`、`VideoUpload/App.cy.ts`、`accountlinks/VideoImportQueue.cy.ts`、`accountlinks/MSGamesVideoImportQueue.cy.ts`、`common/BaseListbox.cy.ts`。
2. `accountlinks/testUtils.ts` 影响 12 个账号关联 spec，共享的 `plugins: [i18n, pinia, PrimeVue]` 已随 c 批次改为 `[i18n, pinia]` 并删除导入；`VideoPlayer/NativePlayer.cy.ts` 的残留注册随 7.2 清理；`common/SelectStyles.cy.ts` 带 Aura preset 并注册真实 DataTable，随最后一个 Paginator Select 退出后改写成 `.base-select` 样式检查。
3. E2E 复用 `cypress/e2e/accountlink.cy.ts`、`profile.cy.ts`、`bugfix/staff-requests.cy.ts`、`tournament.cy.ts`；e 批次已在 `profile.cy.ts` 的「上传录像」用例内补上选择、筛选 / 清除、排序 `aria-sort` 与分页报告断言，不增加额外的初始化与上传次数；跨页选择由 `VideoUpload/Table.cy.ts` 的 27 行数据覆盖。a 的 `/admin/queue` 响应结构变化需同步调整 `cypress/e2e/accountlink.cy.ts` 的 intercept 与表格断言。
4. 每批验收：空数据、加载、默认排序与切换、筛选清除、页容量与跳页、筛选后页码重置、选择 / 展开与独立单元格操作、请求参数与提交次数、深浅主题与窄容器。分页替代至少覆盖首末页、页容量、跳页、总数、过滤后页码处理和数据变化；原生 HTML / CSS 只负责展示，不能替代这些数据和状态逻辑。

##### 5.2.4 最终清理（最后一个使用方退出后）

按代码 → 样式 → 文档 → 依赖的顺序完成：

1. 删除 `bootstrap.ts` 的 `definePreset` / `Aura` / `PrimeVue` 导入与 `app.use(PrimeVue, ...)`；`main.ts` 本身不注册插件，无需改动。清理 `App.vue` 的 `.p-datatable-filter-overlay-popover` / `.p-select-overlay` z-index 补丁。
2. 删除 `vendors/primevue-table.css`、`primevue-table-controls.css`、`primevue-select.css` 及 2 处导入（1 个使用方 + `SelectStyles.cy.ts`）。`styles/parameters/primevue.less` 属 Git 忽略的本地参考存档，只核对无构建依赖，不作为交付物。
3. 从 `package.json` / `package-lock.json` 删除 `primevue`、`@primevue/core`、`@primeuix/themes` 及仅由它们引入的传递依赖；保留 `primeicons` 7.0.0、全部 `primeicons/primeicons.css` 导入点、离线打包脚本与 CDN 样式检查。
4. 同步修正仍称 `main.ts` 注册 PrimeVue / Aura 的 `docs/development.md`、`src/styles/parameters/README.md`，把第 5 节依赖表与「剩余工作」表中的批次 5 标为完成。
5. 全库检索确认 `primevue` / `@primevue` / `@primeuix` 导入与 `.p-*` 选择器归零（`primeicons` 除外），再做生产构建与产物检查；不把局部迁移视为整个项目已退出 PrimeVue。

**顺序与边界**：5.2.4 必须等 `StaffView/Task.vue` 这最后 1 个使用方退出；若 `Task.vue` 长期随管理员任务页维护而暂缓，e 批次后先保留最小注册与依赖，不提前删除。现有 `vendors/primevue-table*.css` 已完成必要的表格过渡适配，不再重复建立这些文件，也不建设完整的 PrimeVue 主题体系；是否提取 `bootstrap.ts` 中的 preset 按实际维护需要决定。a 含后端 API 扩展，前后端改动同批验收；b 已先行实施，a 的列交互契约仍不可跳过。复杂交互确需组件库时，再核对项目现有 Element Plus 组合，不引入新的表格库。

### 6. 暂缓范围、独立页面计划与局部收尾

以下范围保持暂缓：

- 首页比赛卡片 `views/HomeView/NormalTournamentQueue.vue`：当前唯一 ElCard，带 header；按既定范围保留。
- PrimeVue 全量退出：按上一节独立推进，不阻塞本轮其他样式工作。

当前 `eslint.config.js` 的相关规则：

- 基础规则对所有 `**/*.{js,ts,vue}` 禁止新增 ElText、Element Plus 布局组件、ElCard、ElDivider 及 ElCheckbox / ElCheckboxGroup / ElCheckboxButton。
- `src/**/*.vue` 追加禁止 ElButton / ElLink；`ignores` 仅保留 `views/HomeView/NormalTournamentQueue.vue` 一个文件级例外，不扩展为目录豁免。该文件仍有 ElCard 1 处、ElLink 3 处，并靠文件首行的整文件 `eslint-disable vue/no-restricted-html-elements` 放行；`VideoImportQueue.vue` 的失效例外已随 b 批次移除。
- `no-restricted-imports` 按文件清单禁止新增 `primevue/*` / `@primevue/*` / `@primeuix/*` 导入；当前仍直接依赖 PrimeVue 的 5 个文件保留豁免，随最后一批退出逐条删除，不扩展到 `primeicons`。c 批次已移除 `MSGamesVideoImportQueue.vue` 与 `accountlinks/testUtils.ts`，d 批次已移除 `IdentifierView.vue` 与 `IdentifierView.cy.ts`，e 批次已移除 `VideoUpload/Table.vue`、`VideoUpload/Table.cy.ts` 与 `VideoUpload/App.cy.ts` 三条豁免。
- 另有两组文件清单把 ElDescriptions / ElDescriptionsItem 一并加入禁止，含 `views/DatabaseView/VideoView.vue`；第 2 节的 4 个现存调用点不在清单内。
- `vue/no-undef-components` 的图标名称豁免（除 `router-view` 外）随 7.2 清理；全局 `ignores` 中的 `**/GuideView.vue` 已无对应文件，随收尾删除。

这些是按文件保留的兼容范围。迁移某个暂留文件后，同批清理其已不需要的规则例外。每批完成后，删除对应失效导入、重复覆盖及无使用方的兼容样式，并更新剩余清单。复杂组件按功能保留，不以 Element Plus 导入归零作为本轮完成条件。

## 样式组织与冲突控制

- CSS / Less 的选型、styles 下的文件命名及目录组织由实施代理自行决定。每个项目样式目录文件不超过 100 个非空行，注释计入，不通过压缩声明规避限制。
- `src/styles/parameters/` 是 Git 忽略的本地参考存档，应用、测试、其他样式及构建脚本不得依赖它；需要参数时提取到正式样式文件。新检出项目应不需要该目录也能构建。
- 项目参数流向原生组件与库适配。库需要的 `--el-*` / `--p-*` 声明集中在 vendors，由项目变量赋值，不反向读取库变量。
- vendors 样式由实际使用方按需导入，不在 setup.ts、应用启动入口或 Cypress support 全局加载；同时核对库内部的隐式依赖。Select、PrimeVue 表格使用各自的汇总入口，独立路由和组件测试不依赖其他页面预先加载样式。主题及 --ui-* 参数仍全局提供，浮层适配仍用普通全局选择器。
- 优先使用公开 CSS 变量、组件样式接口，再使用局部内部选择器；覆盖集中在适配文件，避免业务页面散落大量覆盖或 `!important`。
- 保持现有文件路径、props、事件、slots 和调用方依赖的 attrs 稳定。按钮保留原生语义、键盘操作、disabled、loading、防重复点击及已有事件透传。
- 每个 PR 限定一个结果和一小组相关文件。共享样式与业务模块迁移可拆开；不同时做本地化调整、搬目录、整文件格式重排或无关逻辑抽离。
- 每批从最新集成分支开始，及时合入；正在频繁修改的业务区域可后移，允许新旧样式共存。
- 修改前核对工作区与最新内容，保留无关改动；两次修改之间发生的不同意的变化按约定添加 TODO，不直接覆盖。下一轮读取 `lintfix` 结果时一并检查其产生的 diff。

具体样式入口和变量说明见[`src/styles/README.md`](src/styles/README.md)。

## 后续批次的验证与验收

按实际改动选择检查范围；已提交或明确验收的批次不重新追加验收待办。

| 范围 | 验收重点 |
| --- | --- |
| 视觉 | 深浅主题、直角、紧凑间距、文字语义、数字对齐、中英文长文本；有色单元格引用主题文字色 |
| 组件宽度 | 固定视口下改变容器宽度，检查伸缩、换行、内部滚动，以及少数布局切换组件的状态保持 |
| 操作 | 键盘焦点、hover、disabled、loading、错误状态、防重复提交 |
| 表格 | 空数据、加载、分页、排序、筛选、选择/展开、列宽与独立单元格操作，按实际使用能力检查 |
| 浮层 | 关闭、焦点、滚动、层级，以及传送到 body 的内部下拉框 |
| 业务 | 请求参数、提交次数、状态持久化、权限与删除确认行为保持一致 |

Codex 的检查遵守[根目录专用工作流](../AGENTS.md#codex-专用工作流)：每轮开始只读取一次上一轮 lintfix / typecheck 的日志及退出码；代码或样式修改结束后后台启动两项检查，日志、退出码、任务记录及其他检查临时文件统一保存在仓库根目录 `.tmp/checks/<轮次>/`，留待下一轮确认，不散放在前端根目录。仅整理 Markdown 时不重跑这些检查。构建及 Vitest 按实际影响范围选择，不把后台启动或静态检查当作浏览器验证通过。

Codex 不主动运行 Cypress，每批提供实际受影响的 spec 命令，优先复用现有覆盖。用户明确要求 Codex 执行时仅运行指定的 Chrome 组件测试，不执行 E2E；不主动启动预览或开发服务器。迁移组件时才调整依赖 `.el-*` / `.p-*` 的测试定位，不提前全量改写。

复用项目现有表格提取、通知关闭和 `cy.shouldBeAbsentOrHidden()` 断言命令；不为低影响样式调整编写重复实现的测试，也不靠修改预期值掩盖实际行为变化。

提交或明确验收后按约定移除对应实施与验收待办；下一批建议始终以本计划的剩余范围及当时实际代码为准。
