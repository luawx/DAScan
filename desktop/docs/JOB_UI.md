# Job UI

任务页通过 `JobService` 和 `PlotDasRemoteClient.list_jobs()` 调用服务器 `plotdas job list`，不解析人类文本。表格字段为 Job ID、项目、状态、进度、创建时间、PID 和失败数，右侧展示服务器返回的完整任务详情。

进入页面时自动读取一次；“刷新任务”按钮可随时手动刷新。存在运行中任务且启用自动刷新时，每 5 秒在工作线程刷新，离开页面即停止定时器，避免阻塞 UI 或产生无意义请求。

2026-09-06 已使用真实任务 `job_20260905T214745_24b99027` 验证 `running`、completed/total、failed、PID、current_window 和嵌套 request 字段。

状态固定为 pending、running、completed、failed、cancelled。UI 不直接拼 CLI 命令。
