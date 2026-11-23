# 开发文档

本文档面向扫雷网前端项目的日常开发、调试、测试和构建。

## 技术栈

- Vue 3 + TypeScript
- Vite
- Vue Router，使用 hash 路由
- Pinia
- vue-i18n
- 原生 HTML / CSS、项目基础组件与 Element Plus；图标使用 PrimeIcons 和 Element Plus 图标
- Axios
- Vitest
- Cypress

## 环境准备

建议使用 Node.js LTS 版本，优先使用 Node.js 22 或更新的 LTS。依赖版本由项目内的 `package-lock.json` 固定。

首次安装或需要更新依赖时：

```bash
npm install
```

在全新环境、CI 或希望严格按 lockfile 复现依赖时，优先使用：

```bash
npm ci
```

项目默认开发服务端口是 `8080`，配置在 [vite.config.ts](../vite.config.ts) 中。

## 编码与终端

项目源码和文档统一按 UTF-8 读取，否则在 Windows 终端会出现乱码。这主要影响依赖终端的 Agent，不影响普遍兼容 UTF-8 的现代IDE。

## 环境变量

Vite 会根据运行模式加载对应的 `.env.*` 文件。

| 文件 | 用途 | API 地址 |
| --- | --- | --- |
| `.env.development` | 默认本地开发 | `http://127.0.0.1:8000` |
| `.env.frontend` | 连接线上前端环境 | `https://openms.top` |
| `.env.openms` | openms 构建环境 | `https://openms.top` |

主要变量：

- `VITE_BASE_API`：Axios 的 `baseURL`，见 [src/http.ts](../src/http.ts)。
- `VITE_API_URL`：业务代码中可使用的 API 根地址。
- `VITE_ARTICLE_PIC_PATH`：文章图片路径前缀。
- `Host`：可覆盖 Vite dev server 的 host，默认 `localhost`。

## 启动开发服务

本地后端开发：

```bash
npm run dev
```

连接 openms.top 服务器（仅能使用部分API）：

```bash
npm run frontend
```

启动后访问 `http://localhost:8080`。Vite 配置了 `server.open = true`，运行命令后通常会自动打开浏览器。

## 项目结构

```text
src/
  assets/          全局样式、图片等静态资源
  components/      可复用组件
  components/common/
                   基础 UI 组件、图标、徽章、旗帜
  components/visualization/
                   数据可视化组件
  components/widgets/
                   业务小组件
  i18n/            国际化配置和语言包
  router/          路由配置
  services/        业务服务封装
  store/           Pinia store
  styles/          全局 CSS
  utils/           通用工具函数
  views/           页面级组件
```

入口文件：

- [src/main.ts](../src/main.ts)：检测浏览器能力，通过后按需加载应用启动模块。
- [src/bootstrap.ts](../src/bootstrap.ts)：创建 Vue 应用，注册当前使用的 Element Plus 图标、Pinia、Router 和 i18n，等待路由及 CDN 样式就绪后挂载。
- [src/App.vue](../src/App.vue)：应用根组件。
- [src/router/index.ts](../src/router/index.ts)：主路由表。
- [src/http.ts](../src/http.ts)：Axios 实例与全局 API 地址配置。

## 路由约定

项目使用 `createWebHashHistory`，线上地址形如 `/#/video`。

主路由在 [src/router/index.ts](../src/router/index.ts) 中维护。较大的功能区会拆分自己的子路由，例如：

- 用户页：`src/views/UserView/routes.ts`
- 后台页：`src/views/StaffView/routes.ts`

新增页面时，优先把页面级组件放在 `src/views` 下；可复用业务组件放在 `src/components` 下。

## 代码块

代码展示统一从 `@/components/common/BaseCodeBlock.vue` 导入，可命名为 `VCodeBlock` 使用。它保留原组件的参数、事件和插槽，统一使用 Highlight.js，并随 `local.darkmode` 切换 StackOverflow 浅色／深色主题。页面无需单独设置 `highlightjs`、`theme` 或 `cssPath`，也不要直接从 `@wdns/vue-code-block` 导入。

主题样式来自本地依赖，以 CSS 文本生成 `data:` URL，避免组件的 `fetch()` 在 Vite 开发环境中取得 JavaScript 模块。

## API 请求

统一 Axios 实例位于 [src/http.ts](../src/http.ts)：

- `baseURL` 来自 `import.meta.env.VITE_BASE_API`
- 默认 `Content-Type` 为 `application/x-www-form-urlencoded`
- `withCredentials` 已开启，用于携带 cookie
- 请求超时为 20 秒

组件中既可以直接导入 `$axios`，也可以通过全局属性 `this.$axios` 使用。新代码更推荐在 `src/services` 中封装业务请求，再由组件调用。

## 状态管理

Pinia 初始化在 `src/store/create.ts`，入口注册在 [src/main.ts](../src/main.ts)。新增共享状态时，优先放在 `src/store` 下，并保持 store 的业务边界清晰。

LocalStorage 也在 `src/store` 定义。

## 国际化

i18n 配置位于 `src/i18n`：

- `src/i18n/index.ts`：创建 i18n 实例
- `src/i18n/locales/*.ts`：语言包

新增页面文案时，同步更新需要支持的语言包。组件内局部文案、fallback 规则和新增语言流程见 [国际化文档](./i18n.md)。

## 组件开发建议

- 组件测试困难，只能依赖端到端测试的页面，放在 `src/views`。页面内的组件，如果不可复用，也放在一起。
- 通用 UI 原子组件放在 `src/components/common`。
- 业务组件放在对应功能目录下，例如 `VideoList`、`VideoUpload`、`visualization`。
- TypeScript单测使用Vitest，测试文件与被测组件放在同目录，命名为 `*.test.ts`。
- 组件测试使用Cypress，测试文件与被测组件放在同目录，命名为 `*.cy.ts`。
- 路径别名 `@` 指向 `src`，见 [tsconfig.json](../tsconfig.json) 和 [vite.config.ts](../vite.config.ts)。

## 测试

项目测试分为 Vitest、Cypress 组件测试和 Cypress e2e 测试。项目内的测试入口和目录约定见 [测试文档](./testing.md)。

运行 Vitest：

```bash
npm run vitest
```

常用 Cypress 命令：

```bash
npx cypress open
npx cypress run
```

运行 Cypress e2e 测试前须启动前端开发服务：

```bash
npm run dev
```

组件测试由 Cypress 启动自己的 Vite dev server，不需要手动执行 `npm run dev`。涉及真实后端流程的 e2e 测试还需要启动后端开发服务。

测试时可能遇到浏览器警告冗余的`data-cy`属性，可以忽略，因为该属性会在生产构建时被移除。

## 代码检查

```bash
npm run lint
npm run lintfix
```

ESLint 配置在 [eslint.config.js](../eslint.config.js)。改动较大时建议运行一次 lint 和相关测试。

## 构建与预览

开发模式构建：

```bash
npm run build:dev
```

openms 模式构建：

```bash
npm run build:openms
```

frontend 模式构建：

```bash
npm run build:frontend
```

本地预览构建产物：

```bash
npm run serve
```

构建产物输出到 `dist`。

## 提交流程建议

1. 明确改动范围，避免混入无关文件。
2. 新增或修改关键功能时，按风险补充或运行相邻的单元测试、Cypress 测试。
