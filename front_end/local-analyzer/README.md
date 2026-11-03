# Analyzer 离线构建与发布

离线入口复用公共 [VideoAnalyzer](../src/components/VideoAnalyzer/README.md)，只将 info slot 换成本地文件选择、语言切换、版本和折叠说明。源码与网站共享 CSS 和 i18n，不作为独立 npm 组件库。

## 本地构建

在 front_end 执行：

```powershell
npm.cmd run build:offline
```

此命令同时生成 Analyzer 与[小游戏离线包](../local-minigame/README.md)；仅构建 Analyzer 时运行 `npm.cmd run build:offline:analyzer`。Analyzer 版本唯一来源为 [version.json](./version.json)。输出：

- 展开目录：dist-offline-analyzer/
- ZIP：OpenMinesweeperVideoAnalyzer-${version}.zip
- 网站下载副本：public/assets/OpenMinesweeperVideoAnalyzer-${version}.zip

解压后双击 index.html，在信息区选择或拖入 EVF、AVF、MVF、RMV。无需本地 HTTP 服务、联网缓存或 Service Worker；导出期间禁止更换文件。

包内包含主 HTML、version.json、README.txt、COPYRIGHT.txt、项目 LICENSE、第三方许可证和中英文 help/。信息区内的 README/COPYRIGHT details 与 ZIP 复制同一份正文；语言切换保存到本地设置。用户说明见 [README.txt](./README.txt)，版本与发布管理见 [VERSIONING.md](./VERSIONING.md)。

## 资源与构建边界

- vite.offline.config.ts 使用 Vite、vite-plugin-singlefile 和 vite-plugin-wasm 内联脚本、CSS、WASM、图标及字体；与小游戏共用 scripts/offline-build.ts 和 scripts/offline-package.mjs 的内联及打包工具。离线依赖图禁止导入网站 HTTP 初始化、用户 store、路由或站内包装页。
- 主 HTML 不通过 file:// fetch 加载运行资源。PrimeIcons 只保留可内联的 WOFF2 字体；帮助是包内相对 HTML，用户主动打开的链接不属于运行资源。
- package-offline-analyzer.mjs 拒绝独立资产、外部脚本/样式和非内联 CSS URL，并检查 WASM 与 SVG favicon 已内联。它生成帮助及版权清单，检查每个已打包依赖都有许可正文，再生成 ZIP 和网站副本。
- ms-toollib 的 npm 包缺少许可正文，使用 [已核对的上游 MIT 声明](../licenses/ms-toollib/README.md) 补齐；升级依赖时须复查。
- 视频导出使用主线程独立解析及渲染，无 Worker 子构建；数据和编码资源的生命周期与在线组件一致。

构建和 ZIP 校验不替代 Chrome/Edge 中真实断网 file:// 验证。浏览器的编码、存储及剪贴板能力以实际运行结果为准。

## 网站构建和下载

npm 的 dev/frontend 及 build:dev、build:frontend、build:openms pre hook 会先生成离线包，随后 Vite 将 public/assets 中的 ZIP 复制到网站 dist/assets。直接运行 Vite CLI 时应先手动构建离线包。

现有 [.github/workflows/build.yml](../../.github/workflows/build.yml) 调用 build:openms，随网站部署 ZIP；当前没有独立的离线 artifact 工作流。不能把本地构建当作已经上传或发布。

部署时 collectstatic 收集 ZIP 到 /root/saolei/static/assets/。项目 Nginx 配置的 `location ^~ /assets/` 直接提供该目录的 Vite 资源；更新服务器配置后先 nginx -t，再重载。网站的下载地址为 `${BASE_URL}assets/OpenMinesweeperVideoAnalyzer-${version}.zip`，发布后应核对 HTTP 200、application/zip 和包内版本。

资源页的 [AnalyzerHelper.vue](../src/views/ResourcesView/AnalyzerHelper.vue) 表格是手动发布历史；确认文件实际可下载后再更新条目。开发中的版本与尚未上传的 ZIP 不自动加入下载历史。生成的 HTML 和 ZIP 保持 Git 忽略。
