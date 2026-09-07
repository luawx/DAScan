# Server Protocol

## Runtime

- SSH endpoint: 当前验证为 `asgroup:1015`（本机 SSH config 将别名解析为 `210.45.127.111`）
- project root: `/cluster/datapool2/xuxy/1.Code/PlotDas`
- CLI launcher in non-interactive SSH: `conda run -n xyenv plotdas`
- default input: `/cluster/datapool4/liaoxl/xinjing_group/das_h5`
- output root: `/cluster/datapool2/xuxy/1.Code/PlotDas/output`

客户端命令都先 `cd` 到 project root。参数和路径使用 POSIX shell quoting。

## Connection probe

1. SSH 执行 `printf connection-ok`。
2. `test -d <project-root>` 检查目录。
3. `<cli-launcher> --help` 检查 CLI。

## Preview

```text
plotdas plot --project PROJECT --start DATETIME --end DATETIME
  --channel-start INT --channel-end INT --filter TYPE --dpi INT
  [--lowcut FLOAT] [--highcut FLOAT]
```

成功 stdout（JSON）：

```json
{"image":"/absolute/server/path.png","metadata":"/absolute/server/path.json"}
```

客户端只解析 JSON，然后通过 SFTP 下载 image 并读取 metadata。非零退出码视为失败；stderr 原文进入可展开详情。

## Jobs

- `plotdas job create ... --window-length SECONDS` → job JSON
- `plotdas job start JOB_ID` → job JSON
- `plotdas job status JOB_ID` → job JSON
- `plotdas job list` → JSON array
- `plotdas job cancel JOB_ID` → job JSON

服务器当前所有上述命令本身已经输出 JSON，不需要额外 `--json`，也不解析诸如 `Completed 1 / 10` 的文本。

## Images

权威记录为 `output/<project>/<YYYYMMDD>/index.json` 和每张图的 sidecar metadata JSON。客户端不根据 PNG 文件名推导完整元数据。

