# Output Format

Default layout:

```text
output/<project>/<YYYYMMDD>/
  images/<HHMMSS_microseconds>_<HHMMSS_microseconds>_ch<start>_<end>.png
  metadata/<same-stem>.json
  index.json
  index.lock
```

Each sidecar is authoritative for one requested window. It records schema version, status, project/plugin version, requested and actual time range, timezone, channels, sampling rate, source files and raw provenance, filter, scale, DPI, image path, creation time, and structured error details. Failed windows have metadata but no image path.

`index.json` contains the current records sorted by start time and channel. Updates use an advisory lock and atomic replacement. A desktop client can recursively read `index.json` files and does not need HDF5 access. Paths below the normal output root are stored relative to that root where possible.

