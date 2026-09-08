# DAScan

DAScan 是一套用于分布式光纤声学传感（DAS）数据批量绘制、远程浏览和事件收藏管理的工具，包含：

- `server/`：部署在计算服务器上的 HDF5 检查、滤波、绘图和批任务 CLI。
- `desktop/`：Windows PySide6 客户端，通过 SSH/SFTP 调用服务器并浏览结果。

## 快速配置

服务器端进入 `server/` 后，在已有 Conda 环境中执行：

```bash
python -m pip install -e . --no-deps --no-build-isolation
plotdas --help
```

桌面端进入 `desktop/` 后执行：

```powershell
conda env create -f environment.yml
conda activate plotdas-desktop
python -m pip install -e .
dascan
```

首次启动后在“设置”页填写 SSH 主机、端口、用户名、服务器项目路径和 CLI 命令。服务器用户的完整部署、数据源配置、批量绘制及客户端使用说明见 [中文使用手册](docs/安装配置与使用.md)。

## 主要功能

- 按时间、通道、滤波和渲染参数生成单张或批量 DAS 图像。
- 默认进入图片浏览页，支持本地缓存、预取、拖拽和 30%–800% 缩放。
- 右侧详情完整显示并自动换行，可在设置中选择展示分组。
- 最近观看历史最多保留 100 条。
- 收藏按组管理，点击收藏项直接定位对应项目、日期和图片。
- 一键按“项目/收藏组”导出事件起止时间文本文件。
- 每个项目默认最多使用 1 GB 磁盘缓存，额度可配置，并支持一键清空。
- 相邻图片采用逐张后台预取，避免一次性集中占用 SSH 带宽。

## 测试

```bash
cd server && pytest
cd ../desktop && pytest
```
