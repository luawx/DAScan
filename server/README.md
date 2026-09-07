# DAScan Server

DAScan Server 是服务器端 DAS HDF5 读取、处理、绘图和 JSON 批任务组件。当前支持新井 legacy-flat 与 PRODML 2.0 数据布局，不包含 GUI 或数据库。

## Environment

```bash
ssh -p 1015 asgroup
cd /cluster/datapool2/xuxy/1.Code/PlotDas
conda activate xyenv
python -m pip install -e . --no-deps --no-build-isolation
```

The source DAS directory is read-only. Default paths and rendering parameters are in `config/default.yaml`.

## Quick start

```bash
plotdas inspect /cluster/datapool4/liaoxl/xinjing_group/das_h5/20230308 --limit 2

plotdas plot \
  --project xinjing \
  --start "2023-03-08 12:00:00" \
  --end "2023-03-08 12:01:00" \
  --channel-start 390 --channel-end 882 \
  --filter bandpass --lowcut 2 --highcut 40 --dpi 200

plotdas job create \
  --start "2023-03-08 12:00:00" --end "2023-03-08 12:03:00" \
  --channel-start 390 --channel-end 882 --window-length 60
plotdas job start JOB_ID
plotdas job status JOB_ID
plotdas job cancel JOB_ID
```

完整中文部署与使用流程见仓库根目录 `docs/安装配置与使用.md`，新增 DAS 格式见 `docs/PLUGIN_API.md`。
