# AGENTS.md

本文件为 AI 编码助手（以及其它自动化工具）提供本仓库的工作约定。在本仓库做任何修改前，请先读完本文件。

## 硬性工作流要求

1. **一切改动都基于上游的 `dev` 分支**（`eee555/open-minesweeper` 的 `dev`，本地对应 `upstream/dev`）。不要基于 `main` 开发。
2. **禁止直接向 `dev` 推送。** 每一次改动都必须通过 Pull Request 提交到上游的 `dev` 分支。
3. 标准流程：

   ```powershell
   git fetch upstream
   git switch -c <topic> upstream/dev      # 从上游 dev 切出特性分支
   # ... 修改、自检、提交 ...
   git push -u origin <topic>              # origin 是个人 fork
   # 然后在 GitHub 上向上游 dev 发起 Pull Request
   ```

4. 不要对 `dev` / `main` 执行 force push。
5. 每个 PR 只做一件事，不要夹带无关的格式化或重构。

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| `back_end/saolei/` | Django 后端（Django + django-ninja + MySQL + Redis） |
| `front_end/` | Vue 3 + TypeScript + Vite 前端，录像解析依赖 ms-toollib（Rust 编译的 WASM） |
| `page_404/`、`src_page_ms404/` | 独立的 404 小游戏页 |
| `.github/workflows/` | CI 定义，提交前自检项即来源于此 |

本地安装与启动的完整步骤见 `README.md` 与 `本地启动.md`。

## 提交前自检（与 CI 保持一致）

后端，工作目录 `back_end/saolei/`：

```powershell
python -m flake8          # 代码风格，配置见 setup.cfg
python manage.py test     # 单元测试，需要可用的 MySQL 与 Redis
```

前端，工作目录 `front_end/`：

```powershell
npm run lint        # ESLint
npm run typecheck   # vue-tsc --noEmit
npm run vitest      # 单元测试
npm run build:openms
```

## 代码约定

- **后端风格由 flake8 强制**，配置在 `back_end/saolei/setup.cfg`。除 flake8 本体外还启用了 bugbear、builtins、commas、comprehensions、datetimez、encodings、import-order（google 风格）、multiline-containers、print、quotes 等插件；已忽略 `E501`、`A003`、`DJ08`、`W504`、`W503`。修改后端前请先读该文件。
- **仓库自带一个本地 flake8 插件** `flake8_plugins.django_save_update_fields`，规则号 `DJM100`：任何 Django 模型实例的 `save()` 调用都必须显式传入 `update_fields=`（`form.save(commit=False)` 除外）。这是硬性要求。
- **前端**必须通过 ESLint 与 `vue-tsc` 类型检查，不要用 `any` 或 `@ts-ignore` 绕过。
- 迁移文件（`*/migrations/*`）被 flake8 排除，但仍需提交。

## 不要提交的内容

`wheels/`、`logs/`、`assets/`、`.venv/`、`node_modules/`，以及任何密钥文件（如 `secrets.json`）。

## 本地依赖

- MySQL：数据库 `saolei`，用户 `root`，密码 `123456`，`127.0.0.1:3306`（见 `back_end/saolei/saolei/settings.py` 的 `DATABASES`）。
- Redis：`127.0.0.1:6379`（见同文件的 `CACHES`）。
- 后端首次运行前需在 `back_end/saolei/` 下创建 `logs/` 与 `assets/` 目录。
- 前端播放器 `flop-player` 需要单独下载并解压到 `front_end/public/flop/`，否则录像播放相关页面不可用。
- 依赖版本在 `requirements.txt` / `requirements-wheels.txt` / `package.json` 中固定，升级请单独走 PR。
