# DASData Interface

`DASData.data` is always a NumPy `float32` matrix with shape `(channel, time)`. Readers must convert source layouts before returning it. Filters use the last axis, and renderers use channel on Y and time on X.

Required fields:

- `start_time`, `end_time`: timezone-aware, half-open interval `[start_time, end_time)`.
- `sampling_rate`: samples per second as a positive float.
- `channels`: integer source-channel identifiers matching the first array dimension.
- `channel_positions`: optional physical positions in metres.
- `channel_spacing`, `units`, `source_files`, `metadata`: provenance and display context.

One `DASData` cannot silently contain gaps, overlaps, multiple sample rates, or incompatible channel layouts. Readers must either return one uniform object or raise a specific `DataReadError`/`DataGapError`.

Xinjing user times use `Asia/Shanghai` wall-clock semantics. PRODML raw offset strings and integer times remain in `metadata` for auditing.

