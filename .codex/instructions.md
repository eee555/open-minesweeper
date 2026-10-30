在排查问题时，可以主动要求我配合，例如运行命令、查看浏览器控制台，等等。

# 后端代码规范

后端位置：`back_end\saolei`。测试参考：
- linter：`.github\workflows\flake8.yml`
- 生产安全：`.github\workflows\BackendSafety.yml`
- 业务逻辑：`.github\workflows\backend.yml`

## API
项目里API分为旧的Django views和新的Ninja API。如需创建API，使用Ninja API。如需修改旧的Django views，直接迁移到Ninja API。

### 权限控制
权限控制统一在 API 层解决，包括登录状态、管理员或站长角色、本人操作限制及目标资源访问权限。service 层不处理权限控制，不重复校验操作者身份或权限。

service 层负责业务逻辑、业务状态、数据有效性和一致性校验。

### 管理员 API 的 CSRF 规范

管理员和站长 API 必须遵守 [管理员 API 的 CSRF 规范](../back_end/saolei/ADMIN_API_CSRF.md)。管理员专用接口复用包含 CSRF 校验的 `staff_required`；站长接口使用 Ninja 会话认证自带的 CSRF；与普通主办方共用的接口使用 `admin_csrf_required` 条件校验。普通用户 API 不新增 CSRF，不启用全局中间件，也不修改普通登录权限装饰器。管理写操作不得使用 GET；前端复用统一管理员 CSRF 拦截器，第三方管理员客户端需维护 Cookie 会话并提交 token。

### Ninja API Schema
输出的Schema如果涉及到模型，优先使用`create_schema`生成。

### 装饰器
装饰器用Ninja提供的`decorate_view`打包。所有的装饰器都需要在API的docstrings开头用无序列表注明。

### 限流
限流用Django的ratelimit装饰器。所有API都需要限流。例外：管理员API不需要限流。

## 换行约定
- 倾向不换行。一定不换行的场景：`import`。
- 一行的长度（除去开头的空格）至少达到80字符才需要考虑换行。例外：Python的后缀条件表达式中，如果有链式表达的嵌套逻辑，例如`[x for x in y if z]`或者`x = y if a else z`，则每层逻辑都需要换行。
- 换行后，倾向于将同类元素（如果顺序不重要）放在同一行。
- 不修改已经存在的代码的换行。
- 若flake8报错，则按照flake8的规则修改。

## 后台任务
后台任务，使用Django 6.0支持的Tasks，后端使用`django-tasks-db`。

## 模型字段定义修改
修改模型字段定义后，使用Django命令自动生成迁移脚本，禁止手动修改迁移脚本。如果某个需求必须手写迁移脚本，请先和用户沟通。

## 临时文件清理
`__pycache__`不需要清理。

## 文档更新
API文档由Ninja API自动生成。

VitePress的更新需求：
- 数据库和缓存操作：`vitepress_doc\guide\development\cache.md`
- 管理命令：`vitepress_doc\guide\development\management-commands.md`
- 信号接收器：`vitepress_doc\guide\development\signals.md`

## APP结构

### 同APP
APP内引用链条：`utils -> models -> services -> api`
- `utils.py`存放APP专有的基础函数和常量。此文件不应当引入同APP的任何其他模块
- `services.py`存放涉及到模型的业务逻辑
- `api.py`存放Ninja API。
- 如果有其他APP的API需要用到的Schema，存放在`schema.py`
- 如果需要Redis缓存，缓存逻辑存放在`cache.py`
- 其他文件命名均使用一般的约定

### 跨APP
- 底层APP，仅提供常量配置和工具函数：`config`, `utils`。
- 基础APP，不引用任何其他APP的模型：`videomanager`, `userprofile`。注意：实际上`userprofile`引用了`msuser`，这是唯一的例外，属于历史遗留问题。
- 顶层APP，负责涉及面非常广的业务逻辑和API：`common`。
- 根APP：`saolei`。

禁止临时引用和循环引用。遇到此类问题时，首先考虑为架构设计问题，其次使用信号接收器，最后考虑用`common`APP。例外：属于common practice的情况，例如在`app.py`中临时引入signals的信号接收器。

# 前端代码规范

前端位置：`front_end`。测试参考
- linter：`.github\workflows\eslint.yml`。由于eslint的插件使用了类型解析，运行用时较长，按下述跨轮工作流处理。
- ts模块：`.github\workflows\vitest.yml`
- vue组件：`.github\workflows\cypress.yml`
- e2e：`.github\workflows\CypressE2E.yml`

## Analyzer 版本管理

修改公共 VideoAnalyzer 或离线包，以及会实际影响它们的共享 CSS、i18n、工具和依赖前，必须阅读并遵守 [Analyzer 版本管理约束](../front_end/local-analyzer/VERSIONING.md)。版本独立维护在 `front_end/local-analyzer/version.json`，按实际影响递增并同步变更记录；网站其他修改及重复构建不自动产生 Analyzer 新版本。

## 预览与开发服务器

除非用户明确要求，不要主动启动预览或开发服务器；完成前端修改后也不需要启动服务供用户预览。

## 换行约定
- 数组、字典、html属性，倾向不换行。换行后，倾向于将同类元素（如果顺序不重要）放在同一行。
- 若eslint报错，则按照eslint的规则修改。
- css应当换行。
- 空行照常。

## 本地化
本地化有两种模式：全局本地化位于`front_end\src\i18n`，用于可复用的messages。不可复用的messages放在vue SFC内部，示例`front_end\src\components\ExperimentalFeature.vue`。注意：SFC内部的本地化尽量往`script`块的末尾放。

SFC本地化的messages代码风格示例：
```ts
const i18nMessages = {
    'zh-cn': { local: {
        // 每条message占一行
    } },
    en: { local: {
        // 每条message占一行
    } },
};

const { t } = useI18n({ messages: i18nMessages });
```

## 管理员页面
管理员页面位于`front_end\src\views\StaffView`。这部分页面设计需要考虑到管理员身份与能力的特殊性：

- 不是面向普通用户，不需要关心UI质量与可读性
- 不需要考虑可复用性与可扩展性
- 代码维护往往是全量重写，以减少代码复杂度为目标

## UI风格偏好

重构分步安排见[前端 UI 风格渐进重构计划](../front_end/UI_REFACTOR_PLAN.md)。以下规则用于新增 UI 和本次涉及的组件，不要求在业务维护中顺带改造无关页面。

### 视觉与布局
- 侧重数据展示与分析，以直角和紧凑布局为主。减少容器内外边距、控件间距和多余行高，提高数据密度，同时保证文字和操作清晰可用。
- 至少完整支持浅色和深色两套主题。主要配色暂时沿用项目当前版本 Element Plus 的对应配色，包括主色、状态色、文字、背景和边框色。
- 不在全局区分宽窄屏布局。各组件根据自身可用宽度，通过伸缩、换行或内部滚动适配；仅少数组件按自身宽度切换布局策略，条件由组件单独定义。
- 文本使用`front_end\src\styles\text.css`的样式。优先复用已有公共样式和基础组件，不重复实现。

### 组件选型
- 简单布局和展示优先使用原生 HTML + CSS，例如容器、行列布局、卡片、分隔线和简单描述列表；普通按钮、链接等优先复用项目基础组件，按需完善其原生实现。
- 涉及复杂内部逻辑的组件继续使用 Element Plus，例如依赖组件库交互逻辑的表格、表单校验、弹窗、Tabs 和复杂选择器。保留行为，重点覆盖圆角、间距和尺寸；优先使用公开 CSS 变量和样式接口。
- 替换组件时，以实际使用的能力为准，保留 props、事件、slots，以及 loading、disabled、键盘操作等行为，不仅按外观判断。
- PrimeVue 逐步弃用，不再作为 Element Plus 不支持时的默认备选，不新增其使用范围。现有依赖表内分页器的 DataTable 及其必要依赖暂留，替代方案验证后再逐表迁移；原有排序、筛选、行选择和展开等行为需保留。
- 展示表格使用 BaseTable（原生 HTML + CSS），允许单元格保留独立的玩家链接、下载链接和录像预览。调用方已有原生表头按钮、状态与后端排序请求时，可通过表头插槽保留，例如扫雷榜的指标选择；简单行点击可直接在调用方的 `<tr>` 上绑定原有处理函数，例如 PB 榜的录像预览，不作为保留组件库的理由。调用方负责键盘触发及单元格独立操作的事件冒泡，BaseTable 不接管交互。依赖组件库内部排序、选择、展开、编辑或复杂联动能力的表格继续保留现有实现，不在展示迁移中重写这些能力。分页器与请求由页面单独维护，后端分页本身不作为保留 ElTable 的理由。
- BaseTable 只封装原生表格、公共样式、滚动容器与空状态，表头和行内容通过插槽提供，不新增排序、筛选、分页或递归列注册体系。迁移时保留单元格组件和业务逻辑，不为符合展示范围而删除现有交互。PrimeVue 表内分页替代方案未验证前，仍不在日常业务维护中顺带重写现有表格。
- PrimeVue Toolbar 暂缓迁移。账号关联卡片留待页面重做时处理，管理员任务页留待后续维护。
- Tooltip 继续使用 vue-tippy 的 Tippy 或已有 BaseTooltip，保持其实现和样式导入方式，不为本轮重构引入预设样式或更换提示库。内容容器无需绑定 ElCard，可随简单组件迁移改为原生 HTML + CSS。
- 图标首选 PrimeIcons，其次 Element Plus 图标；PrimeIcons 与 PrimeVue 组件库分开处理，继续保留。
- 弹窗按需创建，减少不必要的常驻实例。

### 渐进迁移
- 本轮重点是 Element Plus 简单组件替换及保留组件的直角、紧凑样式；PrimeVue 退出单独推进。
- 按组件或业务模块小步迁移，允许新旧实现暂时共存。避免同时批量改名、搬文件或调整业务逻辑，保持调用接口稳定。
- 账号关联页面暂不单独改版；共享组件调整影响到该页面时，只做必要的兼容检查。

## 测试注意事项

### lintfix 和 typecheck 跨轮工作流

- 检查使用的临时文件统一放在仓库根目录 `.tmp/checks/<轮次>/`，按需创建目录。包括 lintfix、typecheck、构建、Vitest 和获准运行的 Cypress 的日志、退出码、任务记录及临时排查文件；禁止散放在 `front_end` 根目录。该目录由 Git 忽略，不作为源码或构建依赖。
- 任务记录应注明轮次、命令、日志及退出码文件路径和任务或进程标识，路径以仓库根目录为基准。仅在结果已读取且不再需要后清理对应轮次目录，不删除仍在运行的任务产物。
- 每轮工作开始时，只检查一次上一轮启动的 `npm run lintfix` 和 `npm run typecheck` 的日志、完成状态及退出码。有错误时先根据结果修改对应文件，然后直接开始本轮任务；不为了确认这些修改而立即重跑检查，也不在本轮反复查询上一轮结果。
- 如果上一轮检查仍在运行，记录其待检查状态后直接开始本轮任务，不等待或轮询；保留任务信息供后续轮次开始时检查，不把仍在运行视为通过。
- 完成本轮前端代码修改后，启动 `npm run lintfix` 和 `npm run typecheck`，保留日志路径、任务或进程标识及对应轮次，然后直接交付，不等待检查完成。PowerShell 下可使用 `npm.cmd`。如果上一轮同一种检查尚未结束，保留已有任务，不重复启动并发检查；不为文档修改启动这些检查。
- 交付时分别注明两项检查已确认的结果或“已启动，结果待下一轮检查”。只有读取到完成日志和退出码后才能报告通过；未启动的检查注明未运行及原因。

### Cypress 执行范围

- 每轮不自动启动或重复运行 Cypress 组件测试，不为组件测试主动发起沙箱外运行审批。默认维护相关 spec 并留下命令供用户运行；只有用户明确要求代理执行时才运行。
- 用户明确要求执行时，使用 `--component --browser chrome --spec` 指定相关 spec，不默认运行全部组件测试；已启动的测试仍保留日志及退出码，完成后如实报告结果。
- 默认使用无头模式，例如 `npx.cmd cypress run --component --browser chrome --headless --spec "src/path/A.cy.ts,src/path/B.cy.ts"`；需要带界面排查时按用户要求执行。
- 代理不要执行 E2E 测试，包括 `--e2e` 和 `cypress/e2e` 下的 spec；E2E 继续由用户运行。
- 如 `ELECTRON_RUN_AS_NODE=1` 阻止 Cypress 启动，允许仅在本次命令的进程环境中移除该变量，不修改系统环境变量；沙箱外运行仍遵守执行工具的审批要求。

### Cypress 沙箱限制处理

- 仅在用户明确要求代理执行 Cypress 时，如沙箱限制 Chrome/Cypress 启动、浏览器子进程或测试所需的本地连接，使用执行工具的沙箱外运行机制：`exec_command` 设置 `sandbox_permissions: "require_escalated"`，在 `justification` 中说明具体限制并申请运行指定的组件测试。已批准的命令规则优先复用；需要新规则时使用限定到组件测试和 Chrome 的前缀，例如 `["npx.cmd", "cypress", "run", "--component", "--browser", "chrome"]`。
- 如需清除 `ELECTRON_RUN_AS_NODE`，在执行工具创建的本次 PowerShell 子进程中先运行 `Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue`，再启动指定的 Cypress 组件测试。此操作只影响该命令及其子进程，不修改系统或用户的持久环境变量。
- 沙箱外运行仍遵守当前执行工具的审批策略。若环境禁止升级或审批被拒绝，记录未运行及具体原因，交付时留下用户可运行的命令；不得改用其他执行器规避审批或把未运行报告为通过。

### 性能
E2E测试速度较慢，请尽量减少初始化与UI操作次数。测试专注于关键内容的显示，不必要为了追求一次成功使用复杂的robust断言。E2E测试由用户运行，元素定位问题由用户手动调整或反馈；组件测试按上述执行范围处理。

### 关闭通知
有些操作会有[通知弹窗](front_end\src\components\Notifications.ts)，它可能会遮挡页面元素导致测试不稳定。用`cy.closeElNotifications()`关闭所有弹窗。

### 本地化
测试不需要设置本地化语言。默认情况下，Cypress组件测试的语言为英文，E2E测试的语言为中文。

### 组件`PlayerName`
该组件用于渲染用户名字，其涉及到复杂的缓存逻辑，因此如果不需要测试其具体内容，应当用`cy.mockPlayerNameFallback()` stub相应的API。

组件测试直接挂载 `PlayerName`，或挂载间接包含它的页面/组件时，必须为每个相关 `cy.mount` 注入项目的 `$axios`：`global.config.globalProperties.$axios`。依赖链 `PlayerName -> PlayerBadge -> UserAvatar` 会读取 `proxy.$axios.defaults.baseURL`；Cypress 组件挂载不执行网站的 `main.ts`，不会自动注册该属性。`cy.mockPlayerNameFallback()` 只拦截 API 请求，不能代替 `$axios` 注入，否则会触发 `Cannot read properties of undefined (reading 'defaults')`，并可能导致测试卡住。

```ts
import $axios from '@/http';
import i18n from '@/i18n';

cy.mockPlayerNameFallback();
cy.mount(ComponentUnderTest, {
    global: {
        plugins: [i18n],
        config: { globalProperties: { $axios } },
    },
});
```

将注入配置合并到已有挂载选项，保留所需的 plugins、stubs 等；测试内的独立挂载、重新挂载和共享挂载 helper 都需要覆盖。仅在相关组件被完整 stub、不渲染上述依赖链时可以省略。

### 表格内容
对于表格文本内容，使用`commands.ts`提供的`cy.getTable`或`cy.extractTableData`实现。

### 临时组件
创建临时测试组件时，用`render`语法，不要用`template`。

# 前后端协调原则
这部分用于辅助思考，不属于强制规范。

- 后端服务器性能较差，带宽较低，单个请求返回体一般不要超过300KB。
- 前端设计上应该采用批量请求数据+本地计算的方式。
- 后端需要即时响应的业务逻辑，应当避免对于数据库的低效查询，这包括不必要的多次查询、对非索引列的排序。如需后端排序，考虑两个解决方案：添加索引、添加缓存。

# VitePress文档风格

除了[开发文档](vitepress_doc\guide\development)外，其他文档都至少需要中文和英文版本。除了开发文档外，其他文档面向的是普通用户，应尽量简洁，避免提及技术细节，削减本就符合常理和直觉的内容，侧重于一些特殊、反直觉的规则。
