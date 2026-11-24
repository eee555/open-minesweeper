# 前端 UI 风格渐进重构计划

制定日期：2026-10-03。现状核对与计划更新：2026-11-23。

本计划只列剩余工作与持续适用的约束。已实现、已提交或已验收的批次不再列为实施或测试待办，也不再重复其迁移细节；已完成控件的模板、参数与复用约定以 [`src/styles/README.md`](src/styles/README.md) 与代码为准。原有批次编号保留，避免后续交流中混淆。

新增 UI 和业务维护优先遵守[根目录前端规范](../AGENTS.md)。管理员页面只承接必要的功能与主题兼容，不安排专门的精细视觉改版。

## 目标与固定约束

- 面向数据展示与分析，以直角、紧凑布局和清晰对齐为主，优先减少多余间距，不以普遍缩小字号代替密度改善。
- 同时支持浅色与深色主题。主要配色沿用已提取的 Element Plus 基准值，应用代码使用项目 `--ui-*`，不直接读取组件库颜色变量。
- 组件根据自身可用宽度伸缩、换行或内部滚动；少数确需切换布局的组件单独制定策略，不设置全站宽窄屏布局分界。
- 简单布局和展示采用原生 HTML + CSS，复用项目已有基础组件。复杂交互保留现有组件逻辑，主要调整样式。
- vue-tippy 保持现有实现及样式导入方式。PrimeVue 已弃用且不再引入，PrimeIcons 单独保留。
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
| 原生分页器 | [`BasePagination.vue`](src/components/common/BasePagination.vue) 与 [`pagination.ts`](src/components/common/pagination.ts) 提供区间按钮、任意起始索引跳转和页容量；模型为 `current-start` / `page-size`，`change` 返回从 1 开始、包含端点的 `{ start, end }`，空结果为 `{ start: 0, end: 0 }`；组件不切片数据或请求 API |
| 录像列表 | [`VideoList/README.md`](src/components/VideoList/README.md) 维护原生表格、表达式列、设置页预览、持久化和调用方分工；后续直接复用，不再安排迁移批次 |
| 展示表格 | [`BaseTable`](src/components/common/BaseTable.vue) 封装原生表格、滚动容器、空状态和插槽；`table.css` 提供行悬停高亮，`table-columns.css` 提供排名、玩家、数值、时间等公共列样式 |
| 表头排序图标与状态 | [`SortIcon`](src/components/common/SortIcon.vue) 按 `aria-sort` 三态统一 PrimeIcons 类名；[`sortState.ts`](src/components/common/sortState.ts) 提供 `SortState`、`sortState(order, active)` 与 `nextSortOrder(order, active, clearedOrder)`，由 `<th :aria-sort>`、`SortIcon :state` 和表头按钮共用。根元素仍为 `<i>`，支持父级 `class` 合并，供 BaseTable 调用方复用，不接管排序状态或请求；`aria-sort` 仍由列头维护，字段写入、分页重置和后端请求仍由调用方负责；`clearedOrder` 传 `-1` 时可承接仅升 / 降两态切换的表 |
| 保留表格的视觉 | `theme/tables.css` 为 BaseTable 与 ElTable 提供统一参数，`vendors/element-plus-table.css` 适配保留的 ElTable |
| Element Plus 按钮兼容 | `vendors/element-plus.css` 为消息确认框、日期与颜色选择器等隐式按钮提供直角覆盖；应用模板中 ElButton / ElLink 已归零 |
| 图标注册 | [`bootstrap.ts`](src/bootstrap.ts) 显式全局注册剩余的 7 个图标；导航已改用 PrimeIcons；组件测试按挂载链注册，7.2 其余范围仍待迁移 |
| 导航布局 | [`Menu.vue`](src/views/Menu.vue) 提供顶栏 / 侧栏设置、单行顶栏溢出菜单与窄容器抽屉；App.vue 将唯一的页面主体放入其插槽，切换布局保留页面实例 |
| 原生 Checkbox | [`checkbox.css`](src/styles/checkbox.css) 与 [`checkbox-buttons.css`](src/styles/checkbox-buttons.css) 由 setup.ts 为应用与 Cypress 加载；原生 input / label + 共用 class，提供直角、主题、选中、半选、悬停、键盘焦点和禁用样式，支持数组多选与按钮外观，无 BaseCheckbox 组件 |
| 原生 Radio | [`choice-buttons.css`](src/styles/choice-buttons.css) 通过 checkbox-buttons.css 加载，提供 radio 按钮 class，与 Checkbox 复用直角、选中、禁用、焦点和主题外观；原生分组与 v-model，无 BaseRadio |
| 原生 Switch | [`switch.css`](src/styles/switch.css) 由 setup.ts 加载，提供原生 checkbox / label 的直角开关外观、普通 / 小尺寸、主题、悬停、焦点及禁用状态，无 BaseSwitch；录像筛选 nfOnly 使用普通 Checkbox 外观 |
| 原生进度滑块 | [`slider.css`](src/styles/slider.css) 由 setup.ts 加载，提供 12px × 20px 沙漏外形及主题参数，原生 range 与 ElSlider 共用；`vendors/element-plus-slider.css` 由使用方按需导入 |
| 原生 Select | [`select.css`](src/styles/select.css) 由 setup.ts 加载，提供 .base-select / --ui-select-*；普通尺寸 28px / 14px，小尺寸 24px / 12px，直角及深浅主题共用，聚焦仅主色边框且优先于 hover，不叠加描边或阴影；无 BaseSelect 组件 |
| 原生 Listbox | [`BaseListbox.vue`](src/components/common/BaseListbox.vue) 自行加载 [`listbox.css`](src/styles/listbox.css)：原生 table / tbody / tr / td + 可聚焦的 radio / checkbox，单选与多选共用同一组件，整行点击即选中、选中行高亮，支持 `#option` 插槽、禁用与空状态；`table` 用 `width:auto` 按内容自动收紧宽度，弹层不再固定 16rem；搜索、清除与分页重置由调用方负责 |
| 保留选择器的视觉 | `vendors/element-plus-select.css` 汇总多选标签和浮层适配，带页容量选择的 ElPagination 使用同一入口，共用 --ui-select-* 参数，均由使用方按需导入 |

当前源码事实，后续批次以此为起点：

- BaseTable 已有 50 个 `.vue` 使用方，覆盖排行榜、个人纪录、软件版本列表、导入队列、上传队列、管理员与数据库页面；[`DatabaseView/VideoView.vue`](src/views/DatabaseView/VideoView.vue) 的录像列表由 [`VideoList/App.vue`](src/components/VideoList/App.vue) 用 BaseTable 渲染。
- 应用模板中 ElButton、ElLink、ElCard、ElCheckbox、ElRadio、ElSwitch、ElText、ElDivider、ElDescriptions 已归零；仍有 4 个 ElTable 使用方和 4 处 ElSelect，分别见第 3 节与 4.2 开头。
- 目前的尺寸是后续评审的起点：基础文字 14px，普通原生按钮内边距 4px × 8px、行高 1.4；表格单元格内边距 4px × 8px、行高 1.4；普通卡片内边距 10px。这些现值已生效，后续按组件类别调整，不再安排“先抄参数但不接入运行时”的步骤。

## 剩余工作与建议顺序

| 批次 | 工作 | 范围与边界 |
| --- | --- | --- |
| 3 | 剩余表格核对 | 其余 4 个 ElTable 根据实际排序、编辑等依赖决定是否保留 |
| 7 | 图标注册迁移 | 剩余 7.2：取消 bootstrap.ts 的 7 个全局注册，同步清理 Cypress 注入与 ESLint 豁免 |
| 4 | 其他控件换肤与尺寸细化 | 4.2.5 剩余 Slider、4.2.6 输入与表单、4.2.7 Tabs、4.2.8 弹窗通知与加载，继续分批推进 |
| 6 | 局部收尾 | 随每批删除失效导入、重复样式和已无使用方的兼容项，更新本计划 |

4.2.5 的不透明度原生迁移及剩余轨道、提示样式，以及图标 7.2 仍可独立推进。

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

`DatabaseView/VideoView.vue` 已由查询构建器加原生 VideoList 渲染，不再列入表格迁移待办。其余表格继续使用已统一的视觉样式，不在本批顺带重写内部排序或编辑逻辑。未来按实际使用能力重新评估，而不以表格名称或是否包含按钮作决定。

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

本阶段继续小批推进，每类先选择代表实例验收，再推广。4.2.2 曾用于导航重做，不复用其编号；已落地控件按样式 README 复用，下面只列剩余工作。仍保留的 ElSelect 调用点为 `UserVideoView.vue` 的模式多选、`GSCAdmin/HistoryVideos.vue` 的录像标识多选、`StaffView/Logs.vue` 的文件搜索和 `StaffView/Medal.vue` 的勋章搜索，分页器内部选择器也保留；它们共用已落地的 --ui-select-* 参数，适配由使用方按需导入。

| 子批次 | 当前范围 | 实施边界 |
| --- | --- | --- |
| 4.2.5 Slider | 3 个文件、3 处 ElSlider；与 Analyzer 原生进度滑块共用的沙漏外形已由 slider.css 提供 | 简单不透明度单独迁移；双滑块及播放器拖动保留组件交互，继续细化轨道和提示样式 |
| 4.2.6 输入与表单 | ElInput 为 17 个文件、33 处，ElInputNumber 为 16 个文件、24 处；另有 6 处 ElForm、20 处 ElFormItem | 先盘点能力和校验依赖，再以登录/注册为换肤试点；不批量替换表单和数值处理 |
| 4.2.7 Tabs | 11 个业务文件、12 处 ElTabs；另有 1 个测试包装组件 | 先验收已有水平换行与逐项选中指示，再细化高度、间距、边框；保留纵向布局和路由状态 |
| 4.2.8 弹窗、通知与加载 | 21 处 ElDialog、2 处 ElDrawer，以及通知和加载调用 | 以 BaseOverlay、登录弹窗、Notifications 为代表，逐类调整内部间距、边角与浮层 |

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

### 6. 局部收尾

首页比赛卡片 `NormalTournamentQueue.vue` 已改为原生 section + card / card-title；标题与比赛入口使用原生链接，刷新使用 BaseTextButton，保留加载遮罩、禁用状态、倒计时和请求行为。该文件的整文件 ESLint disable 及 ElButton / ElLink 文件例外已删除，HomeView.cy.ts 已同步定位。本轮待用户运行首页组件测试并人工验收，完成后移除此段。

当前 `eslint.config.js` 的相关规则：

- 基础规则对所有 `**/*.{js,ts,vue}` 禁止新增 ElText、Element Plus 布局组件、ElCard、ElDivider、ElCheckbox / ElCheckboxGroup / ElCheckboxButton 及 ElDescriptions / ElDescriptionsItem。
- `src/**/*.vue` 追加禁止 ElButton / ElLink，不保留文件例外。
- `no-restricted-imports` 禁止所有 src 下 TS / Vue 文件导入 `primevue`、`primevue/*`、`@primevue/*`、`@primeuix/*`，不保留文件豁免；规则不扩展到 `primeicons`。
- `vue/no-undef-components` 的图标名称豁免（除 `router-view` 外）随 7.2 清理；全局 `ignores` 中的 `**/GuideView.vue` 已无对应文件，随收尾删除。

这些是按文件保留的兼容范围。迁移某个暂留文件后，同批清理其已不需要的规则例外。每批完成后，删除对应失效导入、重复覆盖及无使用方的兼容样式，并更新剩余清单。复杂组件按功能保留，不以 Element Plus 导入归零作为本轮完成条件。

## 样式组织与冲突控制

- CSS / Less 的选型、styles 下的文件命名及目录组织由实施代理自行决定。每个项目样式目录文件不超过 100 个非空行，注释计入，不通过压缩声明规避限制。
- `src/styles/parameters/` 是 Git 忽略的本地参考存档，应用、测试、其他样式及构建脚本不得依赖它；需要参数时提取到正式样式文件。新检出项目应不需要该目录也能构建。
- 项目参数流向原生组件与库适配。库需要的 `--el-*` 声明集中在 vendors，由项目变量赋值，不反向读取库变量。
- vendors 样式由实际使用方按需导入，不在 setup.ts、应用启动入口或 Cypress support 全局加载；同时核对库内部的隐式依赖。保留的 Select、表格适配使用各自的汇总入口，独立路由和组件测试不依赖其他页面预先加载样式。主题及 --ui-* 参数仍全局提供，浮层适配仍用普通全局选择器。
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

实现、提交或明确验收后按约定移除对应实施与验收待办；下一批始终以本计划的剩余范围及当时实际代码为准。
