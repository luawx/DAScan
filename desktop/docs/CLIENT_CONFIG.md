# Client Config

配置保存在 `config/settings.json`，首次运行使用内置默认值；该文件被 Git 忽略。

设置页集中管理服务器、端口、用户名、PlotDas 根目录、CLI 启动命令、私钥路径、连接超时、keepalive、自动重连、后台并发、前后缓存 K、传输队列初始可见性、当前项目和图片数据源。密码只保存在当前 UI 控件内存中，不写入配置或日志。留空私钥时依次使用 SSH Agent、默认密钥和 `~/.ssh/config` 中的 IdentityFile。

连接层默认每 30 秒发送 keepalive，失败后最多重连两次，后台传输并发为 2。设置保存时会取消活动传输并关闭旧会话，下一次操作使用新配置建立连接。

`prefetch_count` 保存“前后缓存 K”，默认 3，可在 0–20 之间调整。`show_transfer_queue` 默认为 false，因此图片页不会因活动任务自动展开传输队列；用户仍可随时点击底部按钮查看。

项目清单位于 `config/projects.yaml`，不在 UI 中写死 xinjing。

`active_project` 表示默认项目；`data_source` 是该项目用于图片浏览的服务器输出目录，例如 `/cluster/datapool2/xuxy/1.Code/PlotDas/output/xinjing`。它会覆盖当前项目清单中的 `server_output`，便于临时切换到另一套输出结果。项目页则负责持久化管理每个项目的默认输入目录、输出目录、插件和说明。
