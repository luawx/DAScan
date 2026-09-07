# Plugin API

Every plugin subclasses `DASPlotPlugin`, declares `name` and `version`, and implements:

```python
def inspect_file(path: Path) -> FileInfo: ...
def read(request: PlotRequest) -> DASData: ...
def process(data: DASData, request: PlotRequest) -> DASData: ...
def render(data: DASData, request: PlotRequest) -> PlotResult: ...
```

`plot(request)` validates the request, calls those stages in order, writes failure metadata on errors, and returns `PlotResult` on success. Each stage is independently callable for tests.

## Contract

- `inspect_file` reads metadata only and reports layout, exact half-open coverage, sample rate, channel count, spacing, sample count, units, and raw provenance.
- `read` locates all covering files, reads only requested slices, validates gaps to half a sample, deterministically trims later duplicate overlap, allows 1.5 samples of acquisition-clock boundary jitter, and returns canonical `(channel, time)` `float32` data. Every overlap trim is recorded in metadata.
- `process` must preserve time/channel coordinates and record transformations.
- `render` accepts only `DASData`; it must not open source HDF5 files.
- User channel ranges are inclusive. User time ranges are half-open.
- Expected user-facing failures derive from `PlotDASError`; messages must identify the invalid value and affected file/range.

To add a plugin, place its adapter below `plotdas/plugin/`, implement the contract, register its project name in `plotdas.registry`, add format fixtures, and document source-specific time semantics.
