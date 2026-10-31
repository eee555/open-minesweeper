# 项目样式与参数

CSS 与 Less 的选型由实施代理自行决定，根据实际重复程度和维护成本选择；无需逐项征求确认。`src/styles/` 下的文件命名、目录划分和组织方式也由实施代理自行决定。

`src/styles/` 下的项目文件每个不得超过 100 个非空行。空行及仅含空白字符的行不计入，注释行计入；超过时按职责拆分文件，不通过压缩多条声明到同一行规避限制。

`parameters/` 是被 Git 忽略的本地参考存档，不属于项目运行时依赖。应用、组件测试、其他样式及构建脚本均不得直接导入、读取或自动汇总该目录；新检出项目不需要此目录也应能正常构建。

需要参考参数时，将实际需要的值及其依赖变量提取到本目录下对应的样式文件，再使用该文件。例如文字字号放入文字样式文件，按钮尺寸放入按钮样式文件，卡片间距放入卡片样式文件；跨组件共享的颜色可按需建立独立主题文件。具体文件名与 CSS / Less 选型由实施代理决定。

提取后的颜色写入本地色值或引用其他项目变量，不直接读取组件库颜色变量。浅色和深色值一起提取，保留必要的状态、尺寸及局部作用域；新增共享文件通过应用与 Cypress 共用的样式入口接入。

全局样式由入口统一加载，组件和其他 CSS / Less 不再重复导入。网站、Cypress 组件测试与离线 Analyzer 使用 `setup.ts`；离线小游戏在 `local-minigame/main.ts` 加载主题、文字和 Checkbox 按钮样式。卡片、布局、链接、表格及图标等未由所有入口统一加载的样式，仍按组件需要导入；不能仅因其他组件也导入就删除。

正式项目变量位于 `theme/`，通过 `setup.ts` 加载 `theme/index.css`，应用与 Cypress 组件测试共用。`colors.css` 定义文字、背景、边框与禁用色，`accents.css` 定义主色及状态色，`metrics.css` 定义当前字号、圆角与过渡参数。初值沿用 Element Plus 2.14.6，深色主题继续由 `html.dark` 切换；此批只替换变量来源，不调整尺寸和密度。

`--ui-text-color-regular-light` / `--ui-text-color-regular-dark` 分别保存浅色 / 深色模式的默认文字色，`--ui-text-color-regular` 根据页面主题引用对应变量。修改默认文字配色时维护这两项来源。`PiecewiseColorScheme` 的有色单元格按背景明暗选择对应模式的默认文字色，透明单元格继续继承父容器颜色；样式保留 CSS 变量引用，主题色调整无需重新创建色阶对象。

项目代码统一使用 `--ui-*`，包括 JavaScript 中的颜色读取。`InputNumber` 的 `--ui-input-*` 与表格的 `--ui-table-*` 支持局部覆盖。组件库要求的 `--el-*` / `--p-*` 声明仅留在 `vendors/` 适配文件，由项目变量向库传值，不反向读取库变量。

`button.css` 保持原有导入路径，按顺序汇总 `buttons/base.css`、`buttons/variants.css`、`buttons/states.css`，分别负责基础布局、类型配色、尺寸与交互状态。

`layout.css` 的 `.layout-row` 用于已有的可换行定位行，`.layout-columns` 用于弹性分栏；`.layout-stack` 提供纵向 flex 布局及默认 1rem 间距，调用方可只覆盖 gap。不要仅因同样使用 flex 就替换专用布局，需保留换行、定位、尺寸及子项约束。样式按组件显式导入，不依赖其他路由先加载。

`vendors/element-plus-tabs.less` 由 setup.ts 加载，统一将顶部 / 底部 ElTabs 标签按容器宽度换行，隐藏滚动箭头并覆盖库写入的横向位移。选中标签使用自身的主色底线，底部标签改为顶线，保留库的焦点样式、切换事件及面板生命周期；单个过长标签可在自身宽度内折行。规则限定于直接所属的水平标签头，不改变左侧 / 右侧纵向 Tabs。公共 Analyzer 与离线页面当前不使用 ElTabs，不受此规则影响。

`navigation/layout.css`、`navigation/items.css` 与 `vendors/element-plus-navigation.css` 由网站 Menu.vue 加载，组件测试使用相同入口，不影响公共 Analyzer 或离线包。前两者负责外壳、Logo、原生链接及焦点状态，组件库变量和菜单浮层适配集中在 vendors。

导航外壳、侧栏、菜单浮层及抽屉共用 36px 行高和 14px 普通文字字号；个人主页文字、导航图标通过独立变量保持 18px。Logo 图标高 36px，文字图片高 28px、四周 margin 为 4px；直接使用裁剪后的 logo2.png 与像素重着色的 logo2-dark.png，不使用 SVG 包装或滤镜。

`local.navigation_layout` 持久化 top / sidebar，默认 top。顶栏为单行，主导航靠左、账号工具靠右，共用一个 ElMenu 和溢出菜单；NavigationItem.primary 标记主导航，CSS 伪元素提供两组之间的弹性空间，不参与库的菜单项宽度测量。常驻侧栏用 max-content 按内容确定宽度，header / toolbar 通过 subgrid 对齐；外壳宽度低于 760px 时改用抽屉。

主导航及抽屉首页仅显示文字。管理、设置、帮助、语言和主题在顶部使用纯图标，溢出后恢复文字；管理用 pi-shield，帮助用 pi-question-circle。语言和主题顶部入口隐藏下拉箭头，语言选项只显示文字，通过主色及 aria-pressed 标示选中状态。功能与验收状态以[UI 重构计划](../../UI_REFACTOR_PLAN.md)及 Menu.vue 为准。

`checkbox.css` 由 `setup.ts` 全局加载，应用与 Cypress 共用；采用原生 checkbox 与关联 label，无 BaseCheckbox 组件。普通模板为 `<label class="checkbox"><input v-model="checked" class="checkbox-input" type="checkbox"><span>选项文本</span></label>`，业务 class 可加在 label 上。`.checkbox` 提供 24px 最小高度、6px 间距与主题文字色，`.checkbox-input` 提供 14px 直角方框、选中标记、hover、focus-visible 与 disabled 状态。选中标记为内嵌 SVG，颜色为白色，其他配色均引用项目变量；强制颜色模式恢复原生外观。数组多选使用 v-model 和绑定的 value，`.checkbox-group` 负责紧凑换行布局；状态来自 input，CSS 不代替模型或 change 逻辑。原生绑定与外观设置分别参考 [Vue 表单绑定](https://vuejs.org/guide/essentials/forms.html#checkbox)和 [CSS appearance](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/appearance)。

半选外观使用 `:indeterminate` 和横线 SVG，与 checked 共用主题和禁用配色。调用方通过 `:indeterminate.prop` 绑定 DOM property，而非同名 HTML attribute，参见 [Vue v-bind](https://vuejs.org/api/built-in-directives.html#v-bind)与 [MDN 半选状态](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/checkbox#indeterminate_state_checkboxes)。上传表头保留“未选时全选全部过滤结果，半选或全选时清空”的规则；激活后在 nextTick 重新同步 checked / indeterminate，覆盖半选清空或空结果点击时派生 checked 不变的情况。表格中无文字的 checkbox 仍有关联 label 与本地化 aria-label。`cy.shouldHaveState()` 直接断言这两个 DOM 属性，以 null 表示半选。

`.checkbox--small` 提供 12px 字号与 20px 最小高度，文本 span 允许在受限宽度内收缩并按全局文字规则换行。注册协议等交互链接放在 label 外并排显示，避免与勾选操作混在一起；保留 input 的完整可访问名称。上传选项的 `@click.stop` 放在 label 上，同时覆盖方框与文字的点击。

`checkbox-buttons.css` 同样由 setup.ts 加载，提供 `.checkbox-buttons`、`.checkbox-button`、`.checkbox-button-input` 与 `.checkbox-button-content`。底层仍是可聚焦的原生 input，选中、禁用和键盘焦点映射到可见的内容框；鼠标点击 label，键盘使用 Tab / Space。`.checkbox-buttons--compact` 保留软件图标按钮的 1px × 3px 内边距，普通变体使用 12px 字号、2px × 6px 内边距；两者均为直角，并按容器宽度换行。强制颜色模式用系统选中色。筛选组件在 nextTick 后显式发出一次数组 change，组件事件不透传为原生 DOM Event，避免重复请求。

`descriptions.css` 提供原生描述列表模板，无独立 Vue 组件：外层 `.description-layout` 为命名查询容器，内部 `<dl class="descriptions">` 每项使用 `<div class="description-item"><dt>标签</dt><dd>值或控件</dd></div>`。调用方直接导入 `@/styles/descriptions.css`，保持条件显示、v-model 与事件绑定。

默认最多三列，随容器宽度低于 48rem / 32rem 减为两列 / 一列；`.description-wide` 始终占整行，`.description-span-2` 在三列布局中跨两列，其余布局中占一列。无边框项内部可换行，避免标签与控件挤压。`.descriptions-bordered` 提供直角网格和标签背景；`.descriptions-small` 保留 12px 统计展示字号，在小于 20rem / 12rem 时减为两列 / 一列。颜色均来自项目变量，不影响子控件的交互与样式。

录像信息浮层的查询容器显式设置 32em 宽度并以 `max-width: 100%` 限制，避免 inline-size containment 在浮层按内容计算宽度时丢失列表的固有宽度。模板和局部响应参考 [MDN 描述列表](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dl) 与 [CSS 容器查询](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries)。

`text.css` 由 `setup.ts` 全局加载，应用与 Cypress 共用。`body` 默认使用项目常规文字色、基础字号和 `overflow-wrap: break-word`，普通文本通过继承获得这些样式；使用 `:where(div, span)` 默认清零 margin / padding，`:where(span)` 默认设置 `vertical-align: middle`，组件自身的样式可覆盖。普通文本无需添加 `.text`；需要覆盖父容器颜色时使用 `.text-regular`，需要不同字号或状态色时保留对应修饰类。已清理可由全局默认覆盖的 `.text` 声明；标题、段落、链接、表单控件及需要固定字号或重置单元格间距的组件仍可使用 `.text`，不删除有实际作用的重置。

辅助文字可组合 `.text-secondary` 与现有 `.text-small`；状态色复用 `.text-primary` / `.text-warning` / `.text-danger` 等，不在业务组件中重复声明相同颜色。字号类只调整字号，颜色类只调整颜色，不隐式修改布局或重置其他属性。

`theme/tables.css` 提供三种表格共用的 `--ui-table-*` 参数，由 `setup.ts` 直接加载，应用与 Cypress 共用。初值保持 BaseTable 现有外观：14px 字号、1.4 行高、4px × 8px 单元格内边距、1px 网格边框及 500 表头字重；颜色引用项目主题，随 `html.dark` 切换。

`vendors/element-plus-table.css` 与 `vendors/primevue-table.css` 将同一参数映射到保留的 ElTable / DataTable，并补齐网格线、表头字重和空状态样式。优先使用安装版本的公开变量，必要规则限定在组件内部，不合并组件库分离的表头/正文表格，不改变滚动、固定列、列宽或业务事件。排序箭头、筛选、选择、展开和焦点反馈保留；选中行与普通悬停行使用不同颜色。缓存设置等已有页面局部尺寸覆盖继续优先。

`vendors/primevue-table-controls.css` 仅紧凑化 DataTable 内的分页及展开按钮，并使用项目颜色和直角；不覆盖独立分页器、表单及传送到表外的筛选弹层。复杂行仍由其输入控件和展开内容决定实际高度，不强制所有表格行等高。适配接口参考 [Element Plus Table](https://element-plus.org/en-US/component/table.html) 与 [PrimeVue DataTable](https://primevue.dev/datatable/)，变量名称以项目安装包为准。

`table.css` 是 BaseTable 的共享展示样式，使用项目变量、紧凑单元格与容器内滚动。单元格默认规则通过 `:where()` 降低优先级，便于文字语义类及局部样式覆盖。独立单元格链接与预览，以及调用方已有的原生表头按钮可以保留；例如扫雷榜由页面维护指标选择和后端排序请求，BaseTable 仅提供表头插槽。简单行点击由调用方直接绑定 `<tr>`，同时处理键盘触发及单元格事件冒泡，例如 PB 榜的录像预览；不向 BaseTable 增加行事件接口。依赖组件库内部排序、选择、展开、编辑或复杂联动等能力的表格继续保留现有实现。

正文行悬停时默认使用 `--ui-fill-color-lighter` 高亮单元格，自动适配深浅主题；表头及 `.base-table-empty-row` 空状态行不参与。悬停规则也使用 `:where()`，保留局部特殊单元格背景的优先级。公共样式不设置整行手形光标，有行点击操作时由调用方自行设置。

`table-columns.css` 提供按列内容复用的公共类，BaseTable 通过 `@/styles/` 别名依次直接导入它和 `table.css`，避免此处相对 CSS `@import` 被 PostCSS 解析到项目根目录。使用 BaseTable 时自动加载。目前密度榜、扫雷榜和 PB 榜共用这些规则，避免页面重复写对齐、宽度或 `nth-child()` 列序号选择器。

| 类名 | 适用列 | 默认样式 |
| --- | --- | --- |
| `table-col-rank` | 排名、序号 | 宽度 3em、居中、不换行 |
| `table-col-player` | PlayerName、玩家名 | 宽度 12em、左对齐 |
| `table-col-mode` / `table-col-prop` | 模式、属性标签 | 宽度 5em、居中 |
| `table-col-bv` | 3BV 等较短数值 | 宽度 3em、右对齐、不换行、等宽数字 |
| `table-col-number` | Time、Bvs、STNB、Pluck 等数值 | 宽度 5em、右对齐、不换行、等宽数字 |
| `table-col-datetime` | 上传时间等日期时间 | 宽度 10em、居中、不换行 |
| `table-col-center` | 模式、分组表头等 | 居中，不规定宽度 |

在对应的原生 `<th>` 和 `<td>` 上使用同一个类，例如 `<th class="table-col-number">Bvs</th>` 与 `<td class="table-col-number">{{ value }}</td>`。这些类只定义外观，不负责计算排名、数值格式化或渲染 PlayerName，也不需要新增列组件。width 为表格自动布局的列宽基准，实际宽度仍受内容和容器影响；只需居中且保留原列宽时使用 `table-col-center`。特殊表格按需要局部覆盖，不通过列的位置推断语义。保留组件库的表格后续按其样式接口单独接入。

按实际使用范围小步提取，不整体搬入组件库参数，也不建立依赖本地存档的统一入口。实施进度见[前端 UI 重构计划](../../UI_REFACTOR_PLAN.md)。
