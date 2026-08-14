# Runtime telemetry

An example can include an execution profile at the bottom of its generated page. The panel
is designed to answer the practical questions that matter for GPU-heavy examples: how long
the run took, where time was spent, how much CPU and memory it used, which GPU ran it, and
how heavily that GPU was used.

## Enable collection

Telemetry is off by default. Enable it in `pyproject.toml`:

```toml
[tool.earth2studio-gallery]
collect_telemetry = true
telemetry_interval = 1.0
```

Or enable it in the MkDocs plugin configuration:

```yaml
plugins:
  - earth2studio-gallery:
      collect_telemetry: true
      telemetry_interval: 1.0
```

The panel is generated only after an example is executed with collection enabled. Run with
`--force` once when enabling telemetry for an existing cache.

## What is shown

- Total wall-clock execution time
- Per-phase average and peak CPU load, plus peak resident memory
- Per-phase host-wide network traffic
- Per-phase GPU utilization, memory, and power traces when `nvidia-smi` is available
- CPU model, system RAM, operating system, and Python version
- GPU model, total memory, driver version, and driver-supported CUDA version

Sampling is deliberately lightweight and configurable. CPU load is calculated from cumulative
CPU time across the UV process tree, then normalized by the execution system's total logical CPU
count. The dashboard therefore reports the example's share of total CPU capacity from 0–100%,
with both its average and peak shown for each phase. CPU time is observed every 0.1 seconds so
short examples do not inherit the meaningless zero returned by a first non-blocking percentage
sample. Raw aggregate process-tree percentages remain in the retained telemetry data.

The configured interval controls the retained resource samples and GPU queries; its minimum is
0.25 seconds, and one second is a useful default for longer GPU examples. GPU metrics are
device-level, which means other workloads on a shared GPU can influence them. Hostnames and
user names are never collected.

## Profile workflow phases

Use standard Jupytext cell tags to separate setup, inference, and plotting. Tags do not alter
normal Python execution and do not require the gallery package inside the example environment:

```python
# %% tags=["e2sg-profile:setup"]
model = load_model()
data = download_inputs()

# %% tags=["e2sg-profile:inference"]
prediction = model(data)

# %% tags=["e2sg-profile:plotting"]
plot(prediction)
```

Each named phase becomes an expandable dashboard section with its own duration, CPU, memory,
network, and GPU metrics. The `inference` section starts expanded; other phases start collapsed.
Repeating the same tag on multiple cells combines those cells into one phase.

The general panel does not show aggregate metric tiles. Total runtime appears beside the
**Profiled phases** heading, before any phase is opened. If an example has no profile tags, no
metric grid is rendered; the compact runtime line appears above the execution environment.

Network receive and send values come from host network-interface counters because portable
per-process counters are not available. They accurately describe a dedicated runner, but may
include unrelated traffic on a shared host. The end-to-end runtime remains visible above the
phase sections so excluding downloads from inference utilization does not hide their cost.

Package and interpreter provenance is stored separately in each retained run's
`environment.json` and `manifest.json`. See
[Cached results and rendering](caching.md#durable-results) for the recorded fields and
provenance boundaries.

## Material theme integration

The dashboard inherits MkDocs Material's semantic CSS variables rather than defining its own
palette. Its accent, surfaces, text, borders, code typography, and elevation follow the
configured Material color scheme automatically, including light and dark palette toggles.
Setting `theme.palette.accent` or defining a custom Material color scheme is enough to restyle
the dashboard with the rest of the documentation site.
