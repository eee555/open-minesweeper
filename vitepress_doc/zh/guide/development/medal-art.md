# 勋章图片与前端着色

源图保存在 `front_end/src/assets/medal-templates/`，发布文件由 `front_end/scripts/build_medal_art.py` 统一生成到 `front_end/public/assets/medals/`。每个系列只发布一张图形 WebP，初／中／高级共用同一底图；颜色由前端实现，数字由 CSS 叠加。禁止按难度、成绩门槛或每种颜色生成整张成品图。

## 模板与生成

当前使用已确认的 17 枚 v3 去外框透明 PNG。生成器直接保留 alpha，不能按黑色或灰色抠背景，也不能在粘贴时重复应用 alpha。八个单难度能力系列保留完整原方形画布，确保副章区域和星级定位不漂移；其他系列按透明边界适配。全部底图导出为 128×128 WebP，`quality=50`、`alpha_quality=45`、`method=6`。

三张独立难度源资源在 `front_end/src/assets/medal-overlays/difficulty/`，保留共同画布，导出为 `difficulty/b.webp`、`i.webp`、`e.webp`，均为 64×64。初级一星、中级二星、高级三星，三星上方一颗、下方两颗。不可按每组有色边界分别裁切，不能把三阶完成误标成高级。

生成时先在临时目录完成所有编码和预算检查，通过后再整体更新发布文件，避免源图或预算错误留下部分发布结果。原始备份与审阅记录保存在 `docs/medal/artwork-drafts/`。

## 颜色、星级与数字

`medalAppearance.ts` 明确配置 24 个单难度能力定义的成绩分组，合计 241 个门槛；门槛值对应后端实际整数单位，不能按阶段序号或 code 尾缀猜测成绩档次。初级 Time 沿用已审阅分组，其他难度和指标按明确配置分组，不宣称相同百分位或排行榜名次。未映射门槛显示中性色。

`medalMaterial.ts` 是用户确认的默认柔和金属曲线。`medalToneFilter.ts` 按颜色共享 SVG 滤镜，采用 sRGB 明暗映射，alpha 不变；保留至多 32 个未使用的临时选色滤镜。新增颜色不增加图片请求。

`MedalArt.vue` 在主体层应用曲线；NF 固定副章由 `medalFixedBadge()` 中手工登记的圆形区域保护，原图单独显示，不在运行时按金色像素猜测可着色区域。新增模板必须重新确认固定区域。独立星级不参与主体换色。主体位置沿用已审阅布局，星级为左 4%、上 0%、宽高 36%。

数字为 HTML/CSS 文字，与图像滤镜分开。完整称号、门槛和色档的可访问名称始终保留。三阶精工、一次性和纪念类沿用固定主题，不附加单难度星级；原始股东的铜银表示资历，保留其特殊规则。

## 自主配色

`medalPalette.ts` 负责版本化配置与校验，`medalPaletteStore.ts` 负责当前观看者的响应式偏好及本地保存。优先匹配 `code + stage` 的个人覆盖，再使用明确成绩色档的颜色。不会改授予条件、玩家数据或其他人的设置。

`MedalPaletteSettings.vue` 复用于勋章页和设置页，提供五档取色器、HEX 即时预览、各系列难度预览、单门槛覆盖、恢复默认、JSON 导入导出。失败导入不覆盖当前配置；无法持久保存时明确提示。各展示入口共享 `MedalArt.vue`，不为名字提示增加逐玩家的完整摘要请求。

## 预算与缓存

- 图形底图每张不超过 8 KiB，星级每张不超过 2 KiB。
- 全部勋章图片合计不超过 160 KiB；六枚底图保守上限仍为 44 KiB。
- 当前 17 张底图共 60,134 字节，三张星级共 2,808 字节，合计 62,942 字节。
- 底图 URL 版本为 `v=6`，星级为 `v=1`；修改同一路径内容后必须更新版本。
- 页面只引用发布图，不直接加载高分辨率源模板。SVG 的第二个固定副章图层复用同一 URL。

## 验证与构建

```powershell
python front_end/scripts/build_medal_art.py
python -m unittest discover -s front_end/scripts -p test_medal_art.py
cd front_end
npm run vitest -- run src/services/medalAppearance.test.ts src/services/medalPalette.test.ts src/services/medalService.test.ts src/services/medalRecolor.test.ts
npm run build:openms
```

按本地 `.codex/instructions.md` 的跨轮检查流程启动 lintfix 和 typecheck，日志放在 `.tmp/checks/`。Cypress spec 已维护，只有用户明确要求代理执行时才运行；代理不运行 E2E。源图透明性、发布尺寸、完整文件清单与资源预算由生成脚本测试覆盖。
