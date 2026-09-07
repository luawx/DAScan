# Server Usage

## Setup

```bash
ssh -p 1015 asgroup
cd /cluster/datapool2/xuxy/1.Code/PlotDas
conda activate xyenv
python -m pip install -e . --no-deps --no-build-isolation
```

## Inspect

```bash
plotdas inspect /path/to/file.h5
plotdas inspect /path/to/date-directory --limit 5
```

Inspection reads HDF5 structure and endpoints, not complete matrices.

## Plot

```bash
plotdas plot --project xinjing \
  --start "2023-03-08 12:00:50" --end "2023-03-08 12:01:10" \
  --channel-start 390 --channel-end 882 \
  --filter bandpass --lowcut 2 --highcut 40 --filter-order 4 \
  --dpi 200
```

Filters are `none`, `bandpass`, `lowpass`, and `highpass`. Cutoffs must be below Nyquist. Scale modes are `percentile` (default: symmetric absolute p99), `absolute`, and `std`. Existing images require `--overwrite`.

## Jobs

```bash
plotdas job create --start "2023-03-08 12:00:00" --end "2023-03-08 12:03:00" \
  --channel-start 390 --channel-end 882 --window-length 60
plotdas job start JOB_ID
plotdas job status JOB_ID
plotdas job list
plotdas job cancel JOB_ID
```

For every readable archive interval, including gaps and acquisition changes:

```bash
plotdas job create-all --channel-start 200 --channel-end 850 \
  --filter bandpass --lowcut 1 --highcut 50 --dpi 400 \
  --window-length 60 --workers 8
plotdas job start JOB_ID
```

Review `jobs/JOB_ID/log.txt` after a failure. Do not edit a running `job.json` manually.

## Configuration

Pass `plotdas --config custom.yaml COMMAND ...`. Precedence is built-ins, YAML, saved job request, then explicit CLI values. Defaults are in `config/default.yaml`.

Memory defaults are an 8 GB in-memory matrix threshold and 64-channel processing blocks, comfortably below the approved 64 GB ceiling. Larger windows use temporary memory maps under `/tmp`, whose files are removed after each image.
