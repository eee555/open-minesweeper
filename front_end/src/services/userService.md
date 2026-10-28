# User Service

`userService.ts` 封装用户资料、用户标识和用户录像列表相关的前端请求逻辑。其中 `fetchUserInfo` 带有 IndexedDB 缓存、缓存失效检查、请求合并和批量请求能力。本文档是针对该缓存机制的说明。

`fetchUserVideos` 继续按查看者与资料版本合并列表请求；`videolist` 返回网站元信息后，由录像服务补全稳定字段。录像缓存独立于用户信息表，接口字段及配置见 [录像信息缓存](./videoService.md)。

- [需求解析](#需求解析)：大致的设计构思、存在的挑战与解决方案。
- [实际流程](#实际流程)：代码中实现的流程简述。
- [特殊细节](#特殊细节)：容易犯的错误或考虑的不周到的地方。
- [配置项](#配置项)：用LocalStorage进行参数配置。
- [失败策略](#失败策略)：覆盖各种异常情况。

## 需求解析
- 用一个IndexedDB表缓存用户信息，主键是id，当前字段和`GetUserInfoResponse`一致。
- 接口`fetchUserInfo(userId: number, immediate = false): Promise<UserProfile>`用于获取用户数据。
- 当`immediate`为`true`时，直接请求单个用户接口`/api/userprofile/info/{userId}`并更新缓存。这个模式适合用户主页等单个用户加载场景，不进入批量队列。
- 接收到如上请求时，首先去缓存里找用户数据，如果找到了直接返回。如果没找到则需要向后端请求数据。
- 为降低请求频率，后端设置了批量请求用户数据的接口`/api/userprofile/infobulk?ids=1,2,3,...`。
- `fetchUserInfo`的调用方包括`PlayerName.vue`，这个组件在各种表格中会批量出现，因此会频繁遇到批量的`fetchUserInfo`调用，需要解决两个问题：
  - 同一个id被批量请求的时候，应当只向后端请求一次。
    - 用`userInfoRequests as Map<number, UserInfoRequest>`保证不会重复请求一个id。
    - 注：实际上批量接口不介意重复id。这个机制是历史遗留问题：在没有批量请求用户数据的接口时，请求单个用户数据的接口有限流。
  - 多个id被同时请求的时候，应当用批量接口向后端请求。
    - 被调用时不立刻向后端请求数据，而是等待一个延迟，再把这段时间收集到的所有id批量请求。批量请求受到URL长度限制，请求的id数量也有限（由`userInfoBatchSize`控制），因此当需要请求的数据超限时，依次发送多个批量请求。批量请求的等待时间由`batchTimer`和`userInfoBatchDelay`控制。批量处理由`async function processUserInfoBatch()`实现。
  - 以上两个问题合并后，还需要注意一点：当批量请求发出时，不要立刻将对应的id从队列里移除，而是要添加一个`inFlight`标记，阻止在请求期间又接收到同一个id的调用。当批量请求响应后，再移除本批次对应的请求。
- 用户信息可能变化，因此缓存也需要更新。是否需要更新由`userInfoLastUpdate`和`userInfoUpdateInterval`控制。
  - 后端提供了请求需要更新的用户的接口`/api/userprofile/infoupdated?since=123456789`，返回在`since`之后更新的用户id列表。因为用户信息更新不频繁，这个列表的长度有限。
  - 如上请求响应后，直接从缓存中移除对应id。
  - 这个机制发生在从缓存中查数据之前。

## 实际流程
- `fetchUserInfo(id)`被调用
  - 如果`immediate`为`true`，直接请求`info/{id}`，写入缓存并**返回**
  - 查看是否需要更新缓存，若需要则先请求`infoupdated`并清空对应的用户缓存
  - 从缓存中查找id，若找到了则直接**返回**
  - 进入函数`enqueueRequest(id)`
    - `userInfoRequests`已存在该id，则直接**返回**对应的`Promise`
    - 将id包装成`Promise`并加入`userInfoRequests`
    - 执行函数`scheduleBatchIfNeeded`，这个函数会启动`batchTimer`，回调指向`processUserInfoBatch()`
    - **返回**`Promise`
  - `fetchUserInfo`职责已完成，接下来等待`batchTimer`调用`processUserInfoBatch()`

- `processUserInfoBatch()`被调用
  - 在`userInfoRequests`中提取出一批需要请求的id
  - 如果没有需要请求的id，则关闭`batchTimer`，**结束函数**
  - 将这一批id状态设置为`inFlight`
  - `infobulk`批量请求这一批用户信息，然后更新缓存，然后更新这一批id的`Promise`。
  - 从`userInfoRequests`中移除本批次处理过的id
  - 如果还有需要请求的id，再次通过函数`scheduleBatchIfNeeded`启动`batchTimer`
  - `processUserInfoBatch`职责完成

## 特殊细节
- 姓名字段可以缓存精确字符串 `hidden`，不新增缓存列或递增数据库版本。后端隐藏偏好与资格变更更新 `date_updated`，其他浏览器仍通过现有 `infoupdated` 流程按正常周期更新姓名。授权与展示规则见 [用户姓名隐藏](../../../back_end/saolei/userprofile/README.md)。
- 本地资料保存成功后调用 `invalidateUserInfo(id)`，只删除该用户的缓存，并递增响应式 `userInfoRevision(id)`。已挂载的 `PlayerName` 会清除旧展示并通过原有批量接口读取公开姓名；本人编辑模型仍保留原始姓名，不把私有资料写入公开姓名缓存。正常情况下不重置全局检查时间或修改一天的检查间隔，刷新页面也不会恢复被删除的旧缓存。
- 请求记录保存发起时的用户版本；失效前发出的响应不能写回旧缓存，等待它的调用方会重新读取当前版本。旧批次结束时仅清理自己的请求，避免误删保存后创建的新请求。IndexedDB 失效失败不撤销已经成功的资料保存；当前会话跳过该用户的旧缓存，并将 `userInfoLastUpdate` 置零供后续清理重试。
- `serviceConfig.userInfoLastUpdate`的初始值是0，此时没有必要请求`infoupdated`，强行请求必然会导致返回所有id，添加不必要的负担。因此实现中直接跳过`infoupdated`，清空整个缓存。这个机制也可以用来在其他需要的时候重置缓存。
- `infoupdated`响应后才创建删除缓存的IndexedDB事务，避免事务在等待网络期间自动提交。事务成功提交后，将`userInfoLastUpdate`设为本次检查开始时的时间；请求或缓存操作失败时保留旧值，以便下次重试。

## 配置项

用户资料缓存相关配置位于 `store.ts`：

| 字段 | 默认值 | 说明 |
| --- | ---: | --- |
| `userInfoUpdateInterval` | `86400000` | 检查缓存失效的周期，默认 1 天 |
| `userInfoLastUpdate` | `0` | 上次成功检查缓存失效的时间戳 |
| `userInfoBatchDelay` | `500` | 用户资料队列批量发送延迟，单位 ms |
| `userInfoBatchSize` | `100` | 单次 `infobulk` 最多请求的用户数量 |

这些配置使用 `@vueuse/core` 的 `useLocalStorage` 持久化，刷新页面后仍会保留。

## 失败策略

- 缓存失效检查失败不会阻止 `fetchUserInfo` 继续执行。
- IndexedDB 读取失败会降级为网络请求。
- `infobulk` 请求失败会 reject 当前批次的所有等待请求。
- IndexedDB 写入失败会被视为当前批次失败，因为写缓存与返回数据目前在同一个 `try` 块中。

