# Architecture

## Data flow

`CLI / Job Manager -> PlotRequest -> plugin registry -> DASPlotPlugin -> DASData -> PNG + JSON`

The CLI only parses requests. The Job Manager only persists state, splits time windows, and invokes the public plugin API. HDF5 interpretation lives in the Xinjing plugin; filtering and rendering operate on `DASData` and do not know HDF5 keys.

## Components

- `plotdas.models`: stable requests, results, filter/scale settings, and canonical data interface.
- `plotdas.plugin.base`: plugin contract and read/process/render orchestration.
- `plotdas.plugin.xinjing`: Xinjing file discovery plus legacy-flat and PRODML adapters.
- `plotdas.plugin.processor`: sample-rate-aware SOS filtering.
- `plotdas.plugin.renderer`: bounded-display-size plotting and atomic PNG output.
- `plotdas.output`: JSON metadata and per-day index with file locking and atomic replacement.
- `plotdas.jobs`: JSON-backed background worker lifecycle.

No core code special-cases Xinjing HDF5 keys. A new project is connected through the plugin registry.

Large matrices exceeding `reader.memory_limit_mb` use a temporary `float32` memory map under `reader.temp_root`. HDF5 reads and filtering operate in channel blocks; filtering is in-place for mapped data, and the temporary file is removed after rendering.
