# Architecture

PlotDas Desktop 是薄客户端，不读取 HDF5，不执行滤波，也不绘制 DAS 数据。

依赖方向固定为 `UI → Application Service → PlotDasRemoteClient → ServerTransport`。UI 只提交 `PlotRequest`；`PlotDasRemoteClient` 是唯一了解服务器 CLI 的组件；`SSHTransport` 和独立的 `SFTPTransport` 负责通信。以后增加 HTTP 时，只需实现 `ServerTransport` 或等价协议适配器，不改 UI。

所有网络调用由 `QRunnable` 在全局 `QThreadPool` 中执行。成功对象或带 traceback 的失败信息通过 Qt Signal 回到主线程。

当前实现覆盖设置、项目 CRUD、连接检测、预览请求、SFTP 下载、本地缓存、服务器日期/index 浏览、可复用图片查看器、`job list` 任务管理，以及本地收藏、备注、标签和浏览历史。

`SessionManager` 维护一个串行化的浏览会话和最多两个可复用传输会话。`TransferQueue` 对当前图片使用高优先级，对相邻预取使用低优先级，并按远程路径与版本去重。目录/index 缓存只存在于当前客户端会话，手动刷新会使对应项目缓存失效。
