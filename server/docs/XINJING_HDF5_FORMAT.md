# Xinjing HDF5 Formats

Read-only inspection on 2026-09-05 found 19,294 `.h5` files: 16,230 named 500 Hz, 1,963 named 4000 Hz, and 1,101 named 5000 Hz. Observed channel populations include 880, 900, and 978. Some files are empty and at least one sampled file could not be opened due to a bad object header.

## Legacy flat layout

Observed on 2023-03-08:

- `MultiwavelengthData`: `(time, channel)`, commonly `(30000, 900)`, `float32`.
- `Time`: timestamp strings such as `20230308120000.016817`.
- `Locus`: channel/distance coordinates.
- scalar `SamplingFreq`, `SpaceInterval`, `Spacecount`, `Timecount`.
- `MetaKeys`, `MetaValues`, `Metaunit` provide redundant acquisition metadata.

A typical file covers roughly one minute at 500 Hz. The plugin uses `Time` rather than assuming the filename is exact.

## PRODML 2.0 layout

- `Acquisition/Raw[0]/RawData`: `(time, locus)`, `float32`.
- `Acquisition/Raw[0]/RawDataTime`: integer microseconds.
- `Acquisition` attributes include `MeasurementStartTime`, `NumberOfLoci`, and `SpatialSamplingInterval`.
- `Acquisition/Raw[0]` attributes include `OutputDataRate`, `NumberOfLoci`, and `RawDataUnit`.

Observed examples include `(500, 880)` at 500 Hz, `(300000, 880)` at 5000 Hz, and `(240000, 978)` at 4000 Hz.

## Time anomaly

PRODML timestamps carry `+00:00`, while their clock fields match the `UTC8` filename and date directory. Per project policy, the plugin preserves the clock fields and labels them `Asia/Shanghai` without adding eight hours. Original values are retained in output metadata.

## Invalid files

Zero-length datasets and unreadable HDF5 files are never treated as valid coverage. The indexer skips unrelated invalid candidates, but a requested interval without readable coverage fails with file-specific diagnostics.

