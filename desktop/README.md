# DAScan

DAScan 是面向 DAS 数据批量绘制、浏览与事件收藏的桌面工具。桌面端基于 Python + PySide6，通过 SSH 调用服务器绘图 CLI，并使用 SFTP 缓存和展示结果。

## 当前能力

- 五页主窗口和左侧导航
- 可视化项目管理：新建、编辑、删除并实时同步其他页面
- SSH Key / Agent / 运行时密码连接
- PlotDas 目录与 CLI 三段式连接测试
- 完整单张预览请求与 JSON 协议解析
- SFTP 图片下载和 metadata 同步
- 项目/日期分层本地缓存
- 浏览服务器已有日期和图片索引，自动跳过失败记录
- WinSCP 风格持久会话、双连接后台传输队列、目录缓存与自动重连
- 字节级下载进度、速度、ETA、取消和相邻图片预取
- 可配置并持久化的前后 K 张图片预取窗口（默认 K=3）
- 设置页集中管理连接、传输并发、预取和队列显示选项，传输队列默认隐藏
- 可复用图片查看器：适应窗口、100%、滚轮缩放、拖动、按钮及左右方向键切换
- 右侧 metadata 按业务含义分组，以中文字段、单位和友好状态展示
- 服务器 `job list` 任务表、手动刷新及运行任务 5 秒后台刷新
- 本地图片收藏、备注、标签、收藏过滤和最近浏览历史
- 重启后恢复上次查看的项目、日期和图片
- 明确错误摘要与可展开 traceback

## 安装和启动

```powershell
cd F:\PlotDas
conda env create -f environment.yml
conda activate plotdas-desktop
pytest
dascan
```

默认配置对应当前已验证服务器：`asgroup:1015`、项目路径 `/cluster/datapool2/xuxy/1.Code/PlotDas`、xinjing 输出目录 `/cluster/datapool2/xuxy/1.Code/PlotDas/output/xinjing`、CLI 命令 `conda run -n xyenv plotdas`。若 SSH 配置或服务器环境变化，可在设置页修改。

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 和 [docs/SERVER_PROTOCOL.md](docs/SERVER_PROTOCOL.md)。
