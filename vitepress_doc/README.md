# VitePress 用户指南

这个目录用于承载扫雷网的独立用户指南站点。

## 本地开发

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
```

构建产物位于 `.vitepress/dist`。当前 `base` 配置为 `/docs/`，适合部署到主站的 `/docs/` 路径下。

## 语言与旧链接

中文源文件放在 `zh/`，英文放在 `en/`，对应 `/docs/zh/…` 和 `/docs/en/…`。语言菜单按相同页面路径切换；缺少目标语言时显示译文缺失页，并提供该页面已有语言的链接，由用户选择。例如尚未翻译的后端管理命令文档，访问英文地址会提示缺少英文版并提供中文版链接，不自动切换语言。

不带语言的地址（包括首页和旧的 `/docs/guide/…`）按浏览器首选语言跳转：`zh` 开头选择中文，其余选择英文。旧链接的 `?lang=zh|en` 仍可明确指定语言；带 `/zh/` 或 `/en/` 的地址优先遵循路径，不受浏览器语言、查询参数或旧的本地存储影响。跳转保留查询参数和锚点。

浏览器所选语言缺少译文时，同样进入该语言的译文缺失页。切换到其他已有语言时也保留查询参数和锚点。

主站的文档链接统一使用不带语言的地址，由 VitePress 分发，不随主站界面语言变化。离线 Analyzer 没有 VitePress 路由，仍按界面语言打开包内帮助。

主站 Nginx 配置也将 `/docs` 重定向到 `/docs/`，保留查询参数；修改该配置后需要重新加载 Nginx。

[`[path].paths.ts`](./[path].paths.ts) 使用 [VitePress 动态路由](https://vuejs.github.io/vitepress/v1/guide/routing#dynamic-routes)，从两个语言目录自动生成不带语言的跳转页，兼容 Nginx 和 GitHub Pages 静态部署。未知页面保留 404，不跳回首页。跳转由浏览器执行，需要启用 JavaScript；跳转页也提供已有语言的入口。新增页面不需要手工维护跳转清单，部署前需要重新构建。

验证语言路由与构建：

```bash
npm test
npm run build
```
