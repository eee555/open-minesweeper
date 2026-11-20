# 录像列表与 tooltip 配置

## 维护入口

| 需求 | 文件 |
| --- | --- |
| 增删表达式基本字段、调整取值及缺失语义 | [videoExpression.ts](../../utils/videoExpression.ts) 的 `videoExpressionFields` 和上下文 |
| 修改预设公式、格式、菜单选项、新增项默认值、两组默认列、tooltip 默认项或预览样本 | [presets.ts](./presets.ts) |
| 修改列结构、校验、名称、求值结果格式 | [columns.ts](./columns.ts) |
| 修改存储规则 | [columnStore.ts](./columnStore.ts) |
| 修改表格筛选、稳定排序和分页 | [videoListData.ts](./videoListData.ts)、[App.vue](./App.vue) |

字段和默认值的调整集中在前两项，编辑器与设置页通过数据驱动，不需要同步修改 UI。

## 配置契约

配置为有序数组。固定模板只有 `type`，取值为 state、software、level、mode、player；表达式列包含 `id/type/key/expr`。id 为独立于显示名称的稳定标识，同一配置内不可重复；默认项使用字段标识，编辑器添加项使用 UUID，重命名、修改表达式或选择预设时保留 id。tooltip 项另有整数 `width: 1 | 2 | 3`，窄容器内跨度不超过实际列数。

| 表达式类型 | 结果及显示 | 列表交互 |
| --- | --- | --- |
| data、data.Nf | 数字；后缀使用 toFixed(N)，校验范围 0–100，菜单提供到 .4f | 按原始数字排序 |
| date | Unix 毫秒、有效日期字符串或 Date，沿用项目已有日期格式和本地时区 | 按时间戳排序 |
| bytes | 非负有限数值，复用 formatBytes 显示字节数（B、KB、MB 等），文件大小预设采用此类型 | 按原始字节数排序 |
| bool | 严格的 true/false，绿勾/红叉 | 全部/true/false 筛选，不排序 |

表格表达式要求相应结果类型；tooltip 的裸 data 还可展示字符串、布尔值、数组和普通对象。字符串预设（state、software、level、mode、rowKey）仅出现在 tooltip 的预设菜单，使用裸 data；表格仍可通过类型选择固定模板。预设菜单统一创建表达式配置，布尔字段使用 bool。名称 key 直接显示，不作为翻译键；默认配置和预设创建时写入当前语言的名称，保存后不随语言切换改变。固定模板沿用模板本地化。

表达式只开放 VideoAbstract 的基本实例字段，不暴露 getter、方法或对象成员。level 为 b/i/e 或自定义等级代码字符串，日期为 Unix 毫秒。不允许赋值及函数定义。衍生指标保留为预设公式，例如 time 使用 timems / 1000；timems 是合法变量，但不单独列入预设菜单。rowKey 预设的本地分支依赖 end_time。修改字段支持后，不自动改写已保存的表达式。

错误、非预期类型及非法日期显示 NaN；tooltip 的真实缺失输入显示 —，保留有效的 0 和 false。部分摘要使用原始字段是否存在判断缺失，不能用 VideoAbstract 构造默认值伪造数据。

## 页面与持久化

| 场景 | localStorage key |
| --- | --- |
| 个人主页、比赛个人页 | video-list-columns:fixed-player |
| 数据库检索、首页最新及待审录像 | video-list-columns:mixed-players |
| 全站 VideoAbstractDisplay 描述区 | video-abstract-description |

组件接口仍为列数组，localStorage 存储 `{ "version": 2, "columns": [...] }`，空数组有效。存储键固定，不随配置版本递增。自定义 serializer 的 read 负责按版本迁移并校验，write 始终输出当前版本；v1 配置对象中的表达式列若没有 id，会生成 UUID，保留名称、公式、格式、宽度和已有 id，迁移成功后原位回写 v2。以后新增迁移分支时集中修改 read；调整预设或默认值无需升级配置版本。

缺失时使用当前默认配置；坏 JSON、无效结构及未知版本保留原始缓存，临时使用默认值，直到用户完成有效编辑。更早的 video-list-config 和带版本号的临时存储键不读取、不导入。配置不修改录像 IndexedDB 缓存，不绑定账号或玩家。

三块编辑器仅出现在设置页，使用 card/card-title、原生控件和无边框表格；支持追加、在指定项前插入、删除及手动编辑表达式。两组表格和 tooltip 预览共用 presets.ts 中的完整固定样本，分别复用 VideoList 和 VideoAbstractDisplay；样本 id/player_id 为 0，不请求实际录像或玩家资料。

## 渲染与数据处理

- 首页及比赛个人页由 VideoList 筛选、排序、分页；个人主页通过 externalFiltering 共享筛选状态，向表格和散点图提供同一筛选结果，VideoList 继续排序分页。
- 数据库页传 displayOnly，只展示页面已查询并切好的 pageRows，不提供表头排序筛选，也不重复分页。设置页预览同样使用 displayOnly，并以 previewable=false 关闭打开录像。
- 处理顺序为筛选 → 排序 → 分页。data/date/bytes 按求值原值排序，非有限值及无效结果在升降序中均置后，同值保留输入顺序。分页保留任意起始索引，筛选和用户切换排序后回到第一条。
- bool 筛选条件存于 VideoListFilters，多个条件取交集，选择 true/false 时排除错误及非布尔结果；全部则不限制。修改活动列表达式时重新筛选，删除或更换类型时清除对应条件。筛选状态不写入列配置。
- 表格排序和 bool 筛选按基础类型与稳定 id 定位列，重命名及插入其他列不改变当前排序、筛选或分页。活动排序列被删除或更换基础类型时清理排序；表达式变化时重新排序并回到第一条，仅更改小数位不重置排序。
- 保留 rowActions、独立单元格操作与鼠标/键盘录像预览；本地 CSV 记录保留行标识、占位显示和播放限制。其他业务仍使用 VideoAbstract 的数值 getter。
- Tooltip 保留原有按需挂载及 fetchVideoInfo 数据加载，传入完整 VideoAbstract 时直接使用。顶部状态、软件、等级、模式摘要保持独立，描述区消费共享配置。

## 验证

Vitest 分别验证字段上下文、预设与默认配置、格式及结构校验、存储、筛选与排序。Cypress 保留设置页增删/校验及两组独立配置、真实预览、列表排序/筛选/分页、个人主页与散点图同步、tooltip 数据加载和缺失值；不为每个默认字段重复编写 UI 测试。

在 front_end 执行相关组件测试（由用户运行）：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/views/SettingView/App.cy.ts,src/components/VideoList/App.cy.ts,src/components/widgets/VideoAbstractDisplay.cy.ts,src/components/VideoPreviewLink.cy.ts,src/views/UserView/UserVideoView.cy.ts,src/views/DatabaseView/VideoView.cy.ts"
```
