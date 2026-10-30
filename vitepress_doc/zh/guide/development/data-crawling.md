---
title: 数据爬取指南 - 开源扫雷网
description: 录像公开数据的全量爬取与增量同步策略，以及接口参数、批量上限和本地数据更新方式。
---

# 数据爬取指南

## 录像数据爬取

本文介绍如何获取公开录像的结构化数据，不包含录像文件下载。匿名 GET 请求即可使用以下接口。字段定义以 Ninja 自动生成的 API 文档为准。

两种策略分别适用于首次建立本地数据集和后续同步：

- **全量爬取**：使用 `infobulk` 获取摘要，按需通过 `detailbulk` 获取详细指标。
- **增量爬取**：使用 `abstractbulk` 刷新网站元信息，通过 `staticdetailbatch` 补全本地缺少的解析字段。

### 接口与请求约定

以下接口均返回 JSON 数组，路径没有结尾斜杠。

浏览器可从任意源通过 GET 匿名跨域读取这些公开接口，不携带跨域凭据。生产 CORS 由 Nginx 维护既有公开 API 白名单，只允许跨域 GET，GET 的预检仍使用 OPTIONS；其他 API 不因此开放。

| 接口 | 参数 | 单次上限 | 返回内容 | 满批响应约值（JSON / gzip） | 当前限流 |
| --- | --- | --- | --- | --- | --- |
| `GET /api/video/infobulk` | `first`、`count` | 2000 个连续 ID | 录像摘要，包含玩家、状态、上传时间和主要成绩字段 | 453 KiB / 62 KiB | 每 IP 每秒 1 次 |
| `GET /api/video/detailbulk` | `first`、`count` | 500 个连续 ID | 更详细的录像数据，包括点击、局面统计和文件大小等 | 252 KiB / 40 KiB | 每 IP 每秒 1 次 |
| `GET /api/video/abstractbulk` | `first`、`count` | 10000 个连续 ID | `id`、`player`、`upload_time`、`state` | 825 KiB / 86 KiB | 每 IP 每 2 秒 1 次 |
| `GET /api/video/staticdetailbatch` | `ids`，逗号分隔的正整数 ID | 100 个 ID | 从录像文件解析得到的稳定字段，包括软件、难度、用时、点击、局面统计和录像内标识等 | 48 KiB / 7.2 KiB | 每 IP 每秒 5 次 |

响应大小按本地公开数据快照、当前响应字段和 Django 的 gzip 等级 6 测算，假设实际返回满批条目，不包含 HTTP 头；`1 KiB = 1024` 字节。客户端需发送 `Accept-Encoding: gzip`，数据分布会影响实际压缩率。

限流按串行爬取、每 IP 平均约 **0.5 Mb/s** 的 gzip 带宽确定，即 62.5 KB/s，约 61 KiB/s。各接口独立设置请求频率：按表中满批样本，持续调用 `abstractbulk`、`infobulk`、`detailbulk`、`staticdetailbatch` 的带宽分别约为 0.35、0.51、0.33、0.29 Mb/s，其中 `infobulk` 按整秒取值，略高于目标。服务端沿用按请求次数和时间窗口限流，实际带宽随响应大小波动。

前三个接口的 ID 范围为 `[first, first + count)`：

- `first` 至少为 1；`count` 限制在 1 至对应接口上限之间，超过上限时会截断。
- 不存在或未公开的录像不返回，也不会向后补足条数。登录本人或管理员时，这三个接口也只返回公开录像；`abstractbulk` 不包含 `ongoing_tournament` 字段。
- 下一批使用 `first += count`，其中 `count` 应是本次实际采用的、不超过上限的请求跨度。不要按返回条数或返回的最大 ID 推进，否则可能反复请求或遗漏区间。

爬取任务应预先给定本轮起止 ID，最后一批缩小 `count`，避免超出任务范围。这些接口不返回全站总数、最大 ID 或更新时间游标；空数组只表示该区间当前没有公开录像，不能作为扫描结束的依据。

建议串行请求，`abstractbulk` 在每次响应完成后至少等待 2 秒，`infobulk`、`detailbulk` 至少等待 1 秒；`staticdetailbatch` 可按 0.25 秒的间隔安排。收到 429 或请求失败时有限重试并保留当前区间的进度，不将请求失败视为空结果。`timems` 的单位是毫秒；可空指标的 `null` 应保留为未知值，不转成 0。

### 全量爬取：infobulk 与 detailbulk

首次建立本地数据集，或需要重新构建全部数据时，按连续 ID 范围读取：

1. 以最多 2000 个 ID 为一个区间，通过 `infobulk` 获取录像索引和摘要，按 `id` 保存。
2. 如需点击、局面统计等详细数据，以最多 500 个 ID 为一个区间，通过 `detailbulk` 补全本地记录。
3. 每批成功保存后再记录进度，失败后从尚未完成的区间继续。

请求示例：

```http
GET /api/video/infobulk?first=1&count=2000
GET /api/video/infobulk?first=2001&count=2000

GET /api/video/detailbulk?first=1&count=500
GET /api/video/detailbulk?first=501&count=500
```

如果目标数据集始终需要详细指标，也可以直接按 500 个 ID 的跨度使用 `detailbulk` 建库，无需先重复获取同批摘要。不同接口的字段集合和录像内标识字段名并不完全相同，应按实际 Schema 规范本地字段。

需要为本地测试环境下载公开数据快照时，可使用已有的 `dangerzone.download_public_data`，入口和断点续传方式见[本地公开数据快照](./management-commands.md#本地公开数据快照)。

### 增量爬取：abstractbulk 与 staticdetailbatch

已有本地数据集后，将数据分为两部分管理：网站元信息随审核、标识绑定等业务变化，解析字段则通常稳定，无需每轮重复下载。

1. 按最多 10000 个 ID 的跨度请求 `abstractbulk`，按 `id` 更新本地的 `player`、`upload_time`、`state`。
2. 从本次返回的 ID 中，选出本地没有记录或缺少目标解析字段的录像。仅有摘要不代表已经具备全部解析字段。
3. 将待补全 ID 去重，每批最多 100 个，通过 `/api/video/staticdetailbatch?ids=...` 获取解析字段，并按 `id` 合并到本地。
4. 已有完整解析数据的录像只更新元信息，不重复请求解析字段。

请求示例：

```http
GET /api/video/abstractbulk?first=1&count=10000
GET /api/video/abstractbulk?first=10001&count=10000

GET /api/video/staticdetailbatch?ids=42,105,8301
```

批量解析响应不保证与请求顺序一致，必须通过 `id` 对应。缺失或无权访问的 ID 不返回；两次请求之间公开状态可能变化，未取得解析数据的录像留待后续重试，不标记为补全成功。

**增量同步仍需扫描历史 ID 范围。** 只从本地最大 ID 之后开始，无法发现旧录像的审核、归属变化，也会遗漏原来未公开、后来公开的比赛录像。`abstractbulk` 没有“仅返回变化项”的过滤参数，因此这里的增量是只补传缺少的解析数据，而非只查询新增 ID。

如需维护当前公开录像集合，以本次成功扫描区间内的 `abstractbulk` 返回 ID 为准，将不再出现的本地条目标记为当前不可见。接口无法区分录像已删除还是未公开；失败区间不能据此移除条目。

解析字段定义或计算方式调整后，应按新的字段定义重新构建受影响的本地数据，不能依靠仅补全新 ID 的流程更新历史解析结果。

### 下载录像文件

`GET /api/video/download/{id}` 和 `GET /api/video/preview?id={id}.evf` 返回当前存储的原文件或 MSRC 容器。读取 `X-Replay-Container-Version`：`0` 为原始字节，正数表示交给 MSRC 解压器处理；具体算法由文件头决定。`Content-Disposition` 中，归档文件名为原文件名加 `.msrc`，解压后去掉该后缀恢复原名。两个响应头均允许跨源读取。

录像摘要和详细指标的结构、原始 `file_size` 及原始内容哈希不因存储压缩改变。网站的下载按钮自动还原原始录像，直接调用文件 API 的客户端需处理两种存储状态。整场及个人比赛录像包下载接口已移除。
