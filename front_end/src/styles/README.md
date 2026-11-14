# 项目样式与参数

CSS 与 Less 的选型由实施代理自行决定，根据实际重复程度和维护成本选择；无需逐项征求确认。`src/styles/` 下的文件命名、目录划分和组织方式也由实施代理自行决定。

`src/styles/` 下的项目文件每个不得超过 100 个非空行。空行及仅含空白字符的行不计入，注释行计入；超过时按职责拆分文件，不通过压缩多条声明到同一行规避限制。

`parameters/` 是被 Git 忽略的本地参考存档，不属于项目运行时依赖。应用、组件测试、其他样式及构建脚本均不得直接导入、读取或自动汇总该目录；新检出项目不需要此目录也应能正常构建。

需要参考参数时，将实际需要的值及其依赖变量提取到本目录下对应的样式文件，再使用该文件。例如文字字号放入文字样式文件，按钮尺寸放入按钮样式文件，卡片间距放入卡片样式文件；跨组件共享的颜色可按需建立独立主题文件。具体文件名与 CSS / Less 选型由实施代理决定。

提取后的颜色写入本地色值或引用其他项目变量，不直接读取组件库颜色变量。浅色和深色值一起提取，保留必要的状态、尺寸及局部作用域；新增共享文件通过应用与 Cypress 共用的样式入口接入。

全局主题、参数、文字及原生控件样式由入口统一加载，组件和其他 CSS / Less 不再重复导入。网站、Cypress 组件测试与离线 Analyzer 使用 `setup.ts`；离线小游戏在 `local-minigame/main.ts` 加载主题、文字和 Checkbox 按钮样式。卡片、布局、链接、表格及图标等未由所有入口统一加载的样式，仍按组件需要导入；不能仅因其他组件也导入就删除。

`vendors/` 的项目适配样式全部由实际使用方按需导入，不在 `setup.ts`、应用启动入口或 Cypress support 统一加载。组件自己声明依赖，保证直接进入路由、单独挂载和异步加载时可用，不依赖之前访问过的页面。样式载入后仍使用普通全局 CSS，以覆盖挂载到 body 的浮层；按需导入不等于 Vue scoped，也不保证离开路由后卸载样式。项目主题与 `--ui-*` 参数继续全局提供，组件库原版基础 CSS 的现有加载方式保留。

按需加载的代表性组件回归覆盖 Select、首页 Tabs、两种表格及导航确认框。在 front_end 下由用户运行：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/common/SelectStyles.cy.ts,src/views/HomeView/HomeView.cy.ts,src/components/VideoUpload/Table.cy.ts,src/components/widgets/IdentifierManager.cy.ts,src/views/Menu.cy.ts"
```

正式项目变量位于 `theme/`，通过 `setup.ts` 加载 `theme/index.css`，应用与 Cypress 组件测试共用。`colors.css` 定义文字、背景、边框与禁用色，`accents.css` 定义主色及状态色，`metrics.css` 定义当前字号、圆角与过渡参数。初值沿用 Element Plus 2.14.6，深色主题继续由 `html.dark` 切换；此批只替换变量来源，不调整尺寸和密度。

`--ui-text-color-regular-light` / `--ui-text-color-regular-dark` 分别保存浅色 / 深色模式的默认文字色，`--ui-text-color-regular` 根据页面主题引用对应变量。修改默认文字配色时维护这两项来源。`PiecewiseColorScheme` 的有色单元格按背景明暗选择对应模式的默认文字色，透明单元格继续继承父容器颜色；样式保留 CSS 变量引用，主题色调整无需重新创建色阶对象。

项目代码统一使用 `--ui-*`，包括 JavaScript 中的颜色读取。`InputNumber` 的 `--ui-input-*` 与表格的 `--ui-table-*` 支持局部覆盖。组件库要求的 `--el-*` / `--p-*` 声明仅留在 `vendors/` 适配文件，由项目变量向库传值，不反向读取库变量。

`button.css` 保持原有导入路径，按顺序汇总 `buttons/base.css`、`buttons/variants.css`、`buttons/states.css`，分别负责基础布局、类型配色、尺寸与交互状态。

`pagination.css` 由 `BasePagination.vue` 按需导入，只描述分页器自身的换行、字段与跳转输入，通用按钮与 Select 参数继续来自 `button.css` / `select.css`。跳转输入复用 `--ui-select-*` 参数保持与小尺寸 Select 一致的高度、边框和焦点反馈；容器较窄时两组控件各自换行，不设置视口断点。分页区间计算集中在 `components/common/pagination.ts`，组件只负责控件、模型同步与 `change` 事件，便于 Vitest 直接覆盖边界。

`videoList.css` 由 `components/VideoList/App.vue` 按需导入，只描述原生录像表格的列头排序按钮、列头筛选按钮、弹层菜单、图标列与行焦点样式；表格、按钮、Select、文字与主题的公共参数继续来自 `table.css` / `theme/tables.css`、`button.css`、`select.css` 和 `text.css`。该表格不复用 PrimeVue 的 `primevue-table*.css`，后者仍由其余表格按需导入。

`select.css` 由 `setup.ts` 全局加载，提供原生单选的 `.base-select`，不新增 Vue 组件。默认最小高度 28px、14px 字号、直角边框与紧凑内边距，尺寸和状态颜色使用 `--ui-select-*` 参数，可在调用方局部覆盖；颜色继续引用深浅主题变量。普通悬停使用灰色边框，鼠标或键盘聚焦时使用主色边框并优先于悬停，不叠加 outline 或 box-shadow。保留系统原生箭头、选项菜单及键盘操作，样式仅作用于显式 class。宽度由调用方控制，公共样式提供 `min-width: 0` / `max-width: 100%`；关联 label 或本地化 aria-label 由调用方提供。保留的复杂选择器通过 vendors 适配复用这些参数，原生选项菜单仍遵循浏览器及系统外观限制，见 [MDN Select](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/select#styling_with_css)。

`vendors/element-plus-select.css` 汇总 `element-plus-select-tags.css`、`element-plus-select-dropdown.css`，分别负责 ElSelect 的闭合控件、多选标签及下拉浮层。使用 ElSelect 或带 `sizes` 的 ElPagination 的组件导入该入口，固定页容量的分页器无需导入。控件复用普通 / 小尺寸参数，标签和搜索输入同步紧凑化，保留标签删除、折叠计数与自然换行增高；浮层统一使用 14px 字号、28px 最小选项高度和项目背景、选中及禁用配色，保留原有滚动高度和键盘行为。浮层通过公开的 `.el-select__popper` 接入，脱离业务容器后仍直接引用全局项目参数；调用方局部覆盖的参数不会自动继承到 body 下的浮层，需要同时通过 `popper-style` 设置。接口与覆盖方式参考 [Element Plus Select](https://element-plus.org/en-US/component/select.html) 与[主题说明](https://element-plus.org/en-US/guide/theming)。

`vendors/primevue-select.css` 由 `primevue-table.css` 汇总加载，使用安装版本 PrimeVue 4 的公开设计参数统一 DataTable 分页器内的 `.p-paginator-rpp-dropdown`，并在 `.p-select-overlay` 上单独设置浮层参数，避免 body 挂载后丢失主题色。当前所有直接使用的 PrimeVue Select 均已迁移，剩余 Select 浮层均来自分页器；不对 Listbox、列筛选浮层或其他表单控件扩展这组规则。保留数值页容量、分页事件和键盘选择，组件样式与动态插入的 Aura 主题共存，见 [Select 文档](https://primevue.org/select/) 和 [Paginator 文档](https://primevue.org/paginator/)。

`.base-select--small` 复用上述状态与主题，将最小高度和字号调整为 24px / 12px，左右内边距使用上下内边距的基准值，默认为 2px。小尺寸方框相对布局位置下移 1px，同时顶部内边距减少 1px、底部增加 1px，补偿内部文字位置并保持与外部文字的对齐；纵向内边距总量及布局占用高度不变。`MSStatSelect` 保留原有指标 props 与字符串模型，前缀通过关联 label 展示，attrs 转交原生 select，change 继续传所选字符串且不因程序更新模型而触发。散点图的三个选择器在原有 24em 区域内按可用宽度伸缩和换行；原生选项菜单无需原有 ElSelect 的全屏 Popper 配置，其他 Tippy 的全屏处理继续保留。

测试原生 Select 的禁用空字符串占位时，使用 `should('have.prop', 'value', '')` 并核对 `selectedIndex`；`have.value` 通过 jQuery 取值，会跳过禁用选项而得到 null，见 [jQuery Select 取值实现](https://github.com/jquery/jquery/blob/3.7.1/src/attributes/val.js)。Vue 绑定 null / undefined 的选项，其原生 DOM value 不保证为空字符串，应按标签或选中项判断，不将 DOM 字符串等同于 Vue 模型。

`layout.css` 的 `.layout-row` 用于已有的可换行定位行，`.layout-columns` 用于弹性分栏；`.layout-stack` 提供纵向 flex 布局及默认 1rem 间距，调用方可只覆盖 gap。不要仅因同样使用 flex 就替换专用布局，需保留换行、定位、尺寸及子项约束。样式按组件显式导入，不依赖其他路由先加载。

`vendors/element-plus.css` 由使用 ElButton 的组件导入；ElMessageBox、ElDatePicker、ElColorPicker 的使用方也导入它，覆盖这些组件隐式创建的按钮，不改变原生 BaseButton 的样式。

`vendors/element-plus-tabs.less` 由包含 ElTabs 的组件导入，统一将顶部 / 底部 ElTabs 标签按容器宽度换行，隐藏滚动箭头并覆盖库写入的横向位移。选中标签使用自身的主色底线，底部标签改为顶线，保留库的焦点样式、切换事件及面板生命周期；单个过长标签可在自身宽度内折行。规则限定于直接所属的水平标签头，不改变左侧 / 右侧纵向 Tabs。公共 Analyzer 与离线页面当前不使用 ElTabs，不受此规则影响。

`navigation/layout.css`、`navigation/items.css` 与 `vendors/element-plus-navigation.css` 由网站 Menu.vue 加载，组件测试使用相同入口，不影响公共 Analyzer 或离线包。前两者负责外壳、Logo、原生链接及焦点状态，组件库变量和菜单浮层适配集中在 vendors。

导航外壳、侧栏、菜单浮层及抽屉共用 36px 行高和 14px 普通文字字号；个人主页文字、导航图标通过独立变量保持 18px。Logo 图标高 36px，文字图片高 28px、四周 margin 为 4px；直接使用裁剪后的 logo2.png 与像素重着色的 logo2-dark.png，不使用 SVG 包装或滤镜。

`local.navigation_layout` 持久化 top / sidebar，默认 top。顶栏为单行，主导航靠左、账号工具靠右，共用一个 ElMenu 和溢出菜单；NavigationItem.primary 标记主导航，CSS 伪元素提供两组之间的弹性空间，不参与库的菜单项宽度测量。常驻侧栏用 max-content 按内容确定宽度，header / toolbar 通过 subgrid 对齐；外壳宽度低于 760px 时改用抽屉。

主导航及抽屉首页仅显示文字。管理、设置、帮助、语言和主题在顶部使用纯图标，溢出后恢复文字；管理用 pi-shield，帮助用 pi-question-circle。语言和主题顶部入口隐藏下拉箭头，语言选项只显示文字，通过主色及 aria-pressed 标示选中状态。功能与验收状态以[UI 重构计划](../../UI_REFACTOR_PLAN.md)及 Menu.vue 为准。

`checkbox.css` 由 `setup.ts` 全局加载，应用与 Cypress 共用；采用原生 checkbox 与关联 label，无 BaseCheckbox 组件。普通模板为 `<label class="checkbox"><input v-model="checked" class="checkbox-input" type="checkbox"><span>选项文本</span></label>`，业务 class 可加在 label 上。`.checkbox` 提供 24px 最小高度、6px 间距与主题文字色，`.checkbox-input` 提供 14px 直角方框、选中标记、hover、focus-visible 与 disabled 状态。选中标记为内嵌 SVG，颜色为白色，其他配色均引用项目变量；强制颜色模式恢复原生外观。数组多选使用 v-model 和绑定的 value，`.checkbox-group` 负责紧凑换行布局；状态来自 input，CSS 不代替模型或 change 逻辑。原生绑定与外观设置分别参考 [Vue 表单绑定](https://vuejs.org/guide/essentials/forms.html#checkbox)和 [CSS appearance](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/appearance)。

半选外观使用 `:indeterminate` 和横线 SVG，与 checked 共用主题和禁用配色。调用方通过 `:indeterminate.prop` 绑定 DOM property，而非同名 HTML attribute，参见 [Vue v-bind](https://vuejs.org/api/built-in-directives.html#v-bind)与 [MDN 半选状态](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/checkbox#indeterminate_state_checkboxes)。上传表头保留“未选时全选全部过滤结果，半选或全选时清空”的规则；激活后在 nextTick 重新同步 checked / indeterminate，覆盖半选清空或空结果点击时派生 checked 不变的情况。表格中无文字的 checkbox 仍有关联 label 与本地化 aria-label。`cy.shouldHaveState()` 直接断言这两个 DOM 属性，以 null 表示半选。

`.checkbox--small` 提供 12px 字号与 20px 最小高度，文本 span 允许在受限宽度内收缩并按全局文字规则换行。注册协议等交互链接放在 label 外并排显示，避免与勾选操作混在一起；保留 input 的完整可访问名称。上传选项的 `@click.stop` 放在 label 上，同时覆盖方框与文字的点击。

当 `.checkbox` 是描述列表 dd 的唯一直接子元素时，使用内容宽度的块级 flex，交由 dd 居中；避免 inline-flex 的行盒基线影响它与前方 dt 标签的垂直对齐，不使用固定像素偏移。其他上下文继续使用行内布局。

`checkbox-buttons.css` 由 setup.ts 加载，并汇总 `choice-buttons.css` 的 Checkbox / Radio 公共外观；离线小游戏沿原有 Checkbox 按钮入口加载同一依赖。`.checkbox-buttons`、`.checkbox-button`、`.checkbox-button-input` 与 `.checkbox-button-content` 保持原有 API，组件不再重复导入共用样式。底层仍是可聚焦的原生 input，选中、禁用和键盘焦点映射到可见的内容框；鼠标点击 label，键盘使用 Tab / Space。`.checkbox-buttons--compact` 对 Checkbox / Radio 按钮内容统一使用 1px × 3px 内边距，普通变体使用 12px 字号、2px × 6px 内边距；两者均为直角，并按容器宽度换行。强制颜色模式用系统选中色。筛选组件在 nextTick 后显式发出一次数组 change，组件事件不透传为原生 DOM Event，避免重复请求。

原生 Radio 复用 `.radio-buttons`、`.radio-button`、`.radio-button-input`、`.radio-button-content`，无 BaseRadio 组件：外层带 `role="radiogroup"` 与可访问名称，内部每项为 `<label class="radio-button"><input v-model="value" class="radio-button-input" type="radio" :name="groupName" :value="option"><span class="radio-button-content">标签</span></label>`。组内共用 name，不同组件实例使用带 useId() 的独立组名；数字选项通过 :value 保持 number。互斥、Tab / 方向键 / Space 由原生控件处理，不编写自定义键盘状态层；选中、禁用、焦点和深浅主题与 Checkbox 按钮共用外观规则，参见 [Vue 值绑定](https://vuejs.org/guide/essentials/forms.html#value-bindings)及 [MDN Radio](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/radio)。

`switch.css` 由 `setup.ts` 全局加载，无 BaseSwitch：`<label class="switch"><input v-model="enabled" class="switch-input" type="checkbox" role="switch" aria-label="开关名称"><span class="switch-track" aria-hidden="true"></span></label>`。可把选项文字放在同一 label 中代替 aria-label；轨道紧随 input，checked / focus-visible / disabled 直接驱动外观。label 整体可点击并触发悬停反馈，底层 input 可聚焦，使用原生 Tab / Space；状态取原生 checked，不额外维护 aria-checked，参见 [WAI checkbox 开关示例](https://www.w3.org/WAI/ARIA/apg/patterns/switch/examples/switch-checkbox/)。默认轨道 32px × 18px、最小交互高度 24px；`.switch--small` 为 28px × 16px、最小高度 20px；轨道与滑块均直角，颜色引用主题，禁用时变淡并保留当前状态，强制颜色模式使用系统色。本地布尔配置直接 v-model；请求、异步受控值与 change 事件按调用方语义单独处理。

`descriptions.css` 提供原生描述列表模板，无独立 Vue 组件：外层 `.description-layout` 为命名查询容器，内部 `<dl class="descriptions">` 每项使用 `<div class="description-item"><dt>标签</dt><dd>值或控件</dd></div>`。调用方直接导入 `@/styles/descriptions.css`，保持条件显示、v-model 与事件绑定。

默认最多三列，随容器宽度低于 48rem / 32rem 减为两列 / 一列；`.description-wide` 始终占整行，`.description-span-2` 在三列布局中跨两列，其余布局中占一列。无边框项内部可换行，避免标签与控件挤压。`.descriptions-bordered` 提供直角网格和标签背景；`.descriptions-small` 保留 12px 统计展示字号，在小于 20rem / 12rem 时减为两列 / 一列。颜色均来自项目变量，不影响子控件的交互与样式。

录像信息浮层的查询容器显式设置 32em 宽度并以 `max-width: 100%` 限制，避免 inline-size containment 在浮层按内容计算宽度时丢失列表的固有宽度。模板和局部响应参考 [MDN 描述列表](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dl) 与 [CSS 容器查询](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries)。

`text.css` 由 `setup.ts` 全局加载，应用与 Cypress 共用。`body` 默认使用项目背景色、常规文字色、基础字号和 `overflow-wrap: break-word`，普通文本通过继承获得这些样式；使用 `:where(div, span)` 默认清零 margin / padding，`:where(span)` 默认设置 `vertical-align: middle`，组件自身的样式可覆盖。普通文本无需添加 `.text`；需要覆盖父容器颜色时使用 `.text-regular`，需要不同字号或状态色时保留对应修饰类。已清理可由全局默认覆盖的 `.text` 声明；标题、段落、链接、表单控件及需要固定字号或重置单元格间距的组件仍可使用 `.text`，不删除有实际作用的重置。

辅助文字可组合 `.text-secondary` 与现有 `.text-small`；状态色复用 `.text-primary` / `.text-warning` / `.text-danger` 等，不在业务组件中重复声明相同颜色。字号类只调整字号，颜色类只调整颜色，不隐式修改布局或重置其他属性。

`theme/tables.css` 提供三种表格共用的 `--ui-table-*` 参数，由 `setup.ts` 直接加载，应用与 Cypress 共用。初值保持 BaseTable 现有外观：14px 字号、1.4 行高、4px × 8px 单元格内边距、1px 网格边框及 500 表头字重；颜色引用项目主题，随 `html.dark` 切换。

`vendors/element-plus-table.css` 与 `vendors/primevue-table.css` 由包含完整 ElTable / DataTable 的组件导入，将同一参数映射到保留的表格，并补齐网格线、表头字重和空状态样式。`primevue-table.css` 同时汇总 `primevue-table-controls.css` 与 `primevue-select.css`，覆盖其分页与页容量选择器，使用方不再逐个导入子文件。优先使用安装版本的公开变量，必要规则限定在组件内部，不合并组件库分离的表头/正文表格，不改变滚动、固定列、列宽或业务事件。排序箭头、筛选、选择、展开和焦点反馈保留；选中行与普通悬停行使用不同颜色。缓存设置等已有页面局部尺寸覆盖继续优先。

`vendors/primevue-table-controls.css` 仅紧凑化 DataTable 内的分页及展开按钮，并使用项目颜色和直角；不覆盖独立分页器、表单及传送到表外的筛选弹层。复杂行仍由其输入控件和展开内容决定实际高度，不强制所有表格行等高。适配接口参考 [Element Plus Table](https://element-plus.org/en-US/component/table.html) 与 [PrimeVue DataTable](https://primevue.dev/datatable/)，变量名称以项目安装包为准。

`table.css` 是 BaseTable 的共享展示样式，使用项目变量、紧凑单元格与容器内滚动。单元格默认规则通过 `:where()` 降低优先级，便于文字语义类及局部样式覆盖。独立单元格链接与预览，以及调用方已有的原生表头按钮可以保留；例如扫雷榜由页面维护指标选择和后端排序请求，BaseTable 仅提供表头插槽。简单行点击由调用方直接绑定 `<tr>`，同时处理键盘触发及单元格事件冒泡，例如 PB 榜的录像预览；不向 BaseTable 增加行事件接口。依赖组件库内部排序、选择、展开、编辑或复杂联动等能力的表格继续保留现有实现。

正文行悬停时默认使用 `--ui-fill-color-lighter` 高亮单元格，自动适配深浅主题；表头及 `.base-table-empty-row` 空状态行不参与。悬停规则也使用 `:where()`，保留局部特殊单元格背景的优先级。公共样式不设置整行手形光标，有行点击操作时由调用方自行设置。

`table-columns.css` 提供按列内容复用的公共类，BaseTable 通过 `@/styles/` 别名依次直接导入它和 `table.css`，避免此处相对 CSS `@import` 被 PostCSS 解析到项目根目录。使用 BaseTable 时自动加载。目前密度榜、扫雷榜和 PB 榜共用这些规则，避免页面重复写对齐、宽度或 `nth-child()` 列序号选择器。

| 类名 | 适用列 | 默认样式 |
| --- | --- | --- |
| `table-col-rank` | 排名、序号 | 宽度 3em、居中、不换行 |
| `table-col-player` | PlayerName、玩家名 | 宽度 12em、左对齐 |
| `table-col-mode` | 模式 | 宽度 5em、居中、不换行 |
| `table-col-prop` | 属性标签 | 宽度 5em、居中 |
| `table-col-bv` | 3BV 等较短数值 | 宽度 3em、右对齐、不换行、等宽数字 |
| `table-col-number` | Time、Bvs、STNB、Pluck 等数值 | 宽度 5em、右对齐、不换行、等宽数字 |
| `table-col-datetime` | 上传时间等日期时间 | 宽度 10em、居中、不换行 |
| `table-col-center` | 模式、分组表头等 | 居中，不规定宽度 |

在对应的原生 `<th>` 和 `<td>` 上使用同一个类，例如 `<th class="table-col-number">Bvs</th>` 与 `<td class="table-col-number">{{ value }}</td>`。这些类只定义外观，不负责计算排名、数值格式化或渲染 PlayerName，也不需要新增列组件。width 为表格自动布局的列宽基准，实际宽度仍受内容和容器影响；只需居中且保留原列宽时使用 `table-col-center`。特殊表格按需要局部覆盖，不通过列的位置推断语义。保留组件库的表格后续按其样式接口单独接入。

按实际使用范围小步提取，不整体搬入组件库参数，也不建立依赖本地存档的统一入口。实施进度见[前端 UI 重构计划](../../UI_REFACTOR_PLAN.md)。

`slider.css` 由 `setup.ts` 加载，提供 `--ui-slider-thumb-*` 参数：12px × 20px 的纵向沙漏，polygon 两侧中部收窄并保留连接处，主色及禁用色引用项目主题，强制颜色模式使用系统色。`vendors/element-plus-slider.css` 仅由三处 ElSlider 使用方导入，只裁剪可见滑块，不改变库的外层拖动命中区域；Analyzer 原生 range 的 WebKit / Firefox thumb 使用同一组参数，并按实际滑块高度居中，原有横向宽度及区间标记位置保持一致。实现参考 [CSS clip-path](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/clip-path)；原有拖动、键盘、提示及双滑块模型继续由各自实现处理。
