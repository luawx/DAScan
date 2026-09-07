# Development

```powershell
cd F:\PlotDas
conda env create -f environment.yml
conda activate plotdas-desktop
pytest
plotdas-desktop
```

离屏 GUI 冒烟测试可设置 `QT_QPA_PLATFORM=offscreen`。真实预览测试建议用 2023-03-08 12:00:00 到 12:01:00、通道 390–882，先在设置页执行连接测试，再到绘图页预览。

修改后运行 `pytest`。远程协议变更必须先更新 `SERVER_PROTOCOL.md` 与 `PlotDasRemoteClient`，不要让页面直接调用 Paramiko。

