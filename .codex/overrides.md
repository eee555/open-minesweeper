# DeepSeek Harness 会话级约束覆盖（优先级高于 `.codex/instructions.md`）

**适用范围：仅限 DeepSeek Harness（DSH）环境。** 本文件是给 DSH 中运行的代理读取的会话约束，不是项目规范的一部分：在其他工具或环境中（例如 Codex、Cursor、VS Code 扩展、人工开发），一律只按 [instructions.md](instructions.md) 执行，本文件不生效、不得被引用为项目约定。

即使是在 DSH 中，本文件也只覆盖下面明确列出的条目。**与 [instructions.md](instructions.md) 冲突时，仅对冲突的那一条以本文件为准**；本文件未涉及的内容，仍按 `instructions.md` 执行。

除第 1 条改变执行等待方式外，本文件不放宽任何代码、权限、安全或架构约定。

## 1. lintfix 与 typecheck：等待完成并迭代修复（仅 DSH）

替代 `instructions.md`「测试注意事项 → lintfix 和 typecheck 跨轮工作流」。原文的“启动后直接交付、不等待、下轮再看结果”**在 DSH 中不再适用**；其他环境仍按原文执行。

- 完成前端代码修改后，在 `front_end` 依次运行 `npm.cmd run lintfix` 与 `npm.cmd run typecheck`，**同步等待两者结束**，读取退出码和日志。
- 有报错就按 ESLint / vue-tsc 的规则修对应文件，然后再跑，**循环到两项都通过**为止，才能交付。
- 每轮检查的日志、退出码和命令记录仍放在仓库根目录 `.tmp/checks/<轮次>/`，不散放在 `front_end` 根目录，理由与原文一致。
  - 已知限制：截至 2026-11-02，`.tmp` 目录在沙箱内**不可写**（`Access to the path ... is denied`）。若仍不可写，把日志放到可临时替代的位置并在交付时说明，不要为此改项目结构或提交日志文件。
  - 实测（2026-11-02）：`npm.cmd run typecheck` 与 `npm.cmd run lintfix` 在沙箱内均可完整跑通，退出码分别为 0，且未自动改动任何文件；当时 `lintfix` 只有 4 条既有 warning（`useAnalyzerState.test.ts` 的 `vue/one-component-per-file`）。
- 仍然只为实际改动的范围负责：不顺手修复本次改动之外的既有告警；与本次改动无关的既有错误，单独列出并说明不是本轮引入的。
- 纯文档（`.md`）改动仍然不启动这两项检查。

## 2. Cypress：仍由用户运行（仅 DSH）

维持 `instructions.md`「Cypress 执行范围」「Cypress 沙箱限制处理」的原规则，不改为代理自行运行。本节只是把 DSH 中的实测结论与用户决定记录下来，**不构成对其他环境的约定**。

- 每轮不自动启动或重复运行 Cypress 组件测试，不为组件测试主动发起沙箱外运行审批。
- 默认只维护相关 spec，并在交付时留下用户可直接运行的无头命令，例如：
  `npx.cmd cypress run --component --browser chrome --headless --spec "src/path/A.cy.ts,src/path/B.cy.ts"`
- 只有用户当轮明确要求代理执行时才运行；仍然不执行 E2E（`--e2e`、`cypress/e2e` 下的 spec 一律由用户运行）。
- 未经用户要求而已经尝试运行的记录：如实报告跑过哪些 spec、结果和原因，并清理产生的截图等临时产物，不把未运行或未通过写成通过。

### DSH 实测记录（供以后在 DSH 中排查参考）

用户曾一次性允许尝试，结论是**当前 DSH 环境跑不了，已按用户要求停止此类尝试**：

- Cypress 16.2.0 与 Chrome 156 能在沙箱外正常启动，问题不在浏览器。
- 默认沙箱内 Vite 加载配置时 `spawn EPERM`（DSH 沙箱禁止子进程管道），导致 dev server 无法编译，Cypress 报 `Failed to fetch dynamically imported module: .../cypress/support/component.ts`，所有组件 spec 一律失败。
- 即使在 DSH 沙箱外运行，该 spec 仍以同样的动态导入错误失败；`BaseTable.cy.ts`、`BaseButton.cy.ts` 均可复现。
- 因此这类失败**不代表代码有问题**，不要据此修改业务代码；在 DSH 中需要真实结论时交给用户运行。

## 3. 仍然不变的部分（所有环境）

- 权限与安全：权限控制只在 API 层、service 层不重复校验；管理写接口遵守 `ADMIN_API_CSRF.md`；`makemigrations` 生成迁移，禁止手改迁移脚本。
- 不主动启动预览或开发服务器。
- Analyzer 版本管理按 `front_end/local-analyzer/VERSIONING.md` 执行。
- 环境限制如实报告，不把未运行、未验证的项目写成通过。
