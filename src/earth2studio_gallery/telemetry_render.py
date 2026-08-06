from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .parser import cells, markdown
from .runner import RunResult


def telemetry_panel(result: RunResult, source: Path) -> str:
    telemetry = result.telemetry
    summary = _mapping(telemetry.get("summary"))
    system = _mapping(telemetry.get("system"))
    samples = _mappings(telemetry.get("samples"))
    gpus = _mappings(telemetry.get("gpus"))
    if not summary:
        return ""

    metrics = [
        _metric("Runtime", _duration(summary.get("duration_seconds")), "Wall-clock", "", samples),
        _metric(
            "CPU",
            _percent(summary.get("average_cpu_percent")),
            f"Peak {_percent(summary.get('peak_cpu_percent'))}",
            "cpu_percent",
            samples,
        ),
        _metric(
            "Process memory",
            _bytes(summary.get("peak_rss_bytes")),
            "Peak resident set",
            "rss_bytes",
            samples,
        ),
    ]
    if gpus:
        total_gpu_memory = sum(_number(item.get("memory_total_mb")) for item in gpus)
        metrics.extend(
            [
                _metric(
                    "GPU utilization",
                    _percent(summary.get("average_gpu_percent")),
                    f"Peak {_percent(summary.get('peak_gpu_percent'))}",
                    "gpu_percent",
                    samples,
                    ceiling=100,
                ),
                _metric(
                    "GPU memory",
                    _megabytes(summary.get("peak_gpu_memory_mb")),
                    f"of {_megabytes(total_gpu_memory)}",
                    "gpu_memory_mb",
                    samples,
                    ceiling=total_gpu_memory,
                ),
                _metric(
                    "GPU power",
                    _watts(summary.get("peak_gpu_power_watts")),
                    "Peak draw",
                    "gpu_power_watts",
                    samples,
                ),
            ]
        )

    hardware = [
        ("CPU", str(system.get("cpu", "Unknown"))),
        ("GPU", _gpu_models(gpus)),
        ("System RAM", _bytes(system.get("ram_total_bytes"))),
        ("Platform", str(system.get("os", "Unknown"))),
        ("Python", str(system.get("python", "Unknown"))),
        ("GPU driver / CUDA", _gpu_software(gpus)),
    ]

    metric_html = "".join(metrics)
    hardware_html = "".join(
        f'<div class="e2sg-hardware-item"><span>{html.escape(label)}</span>'
        f"<strong>{html.escape(value)}</strong></div>"
        for label, value in hardware
    )
    timing_html = _cell_timings(result, source)
    return (
        '<section class="e2sg-telemetry" aria-labelledby="e2sg-telemetry-title">'
        '<div class="e2sg-telemetry-heading"><div>'
        '<span class="e2sg-eyebrow">Execution profile</span>'
        '<h2 id="e2sg-telemetry-title">Runtime telemetry</h2></div>'
        f'<span class="e2sg-sample-count">{len(samples)} samples</span></div>'
        f'<div class="e2sg-metric-grid">{metric_html}</div>'
        f"{timing_html}"
        '<h3 class="e2sg-telemetry-subtitle">Execution environment</h3>'
        f'<div class="e2sg-hardware-grid">{hardware_html}</div></section>'
    )


def _metric(
    label: str,
    value: str,
    context: str,
    key: str,
    samples: list[dict[str, Any]],
    ceiling: float | None = None,
) -> str:
    chart = _sparkline(samples, key, ceiling) if key else '<div class="e2sg-spark-empty"></div>'
    return (
        '<div class="e2sg-metric"><span class="e2sg-metric-label">'
        f"{html.escape(label)}</span><strong>{html.escape(value)}</strong>"
        f'<span class="e2sg-metric-context">{html.escape(context)}</span>{chart}</div>'
    )


def _sparkline(samples: list[dict[str, Any]], key: str, ceiling: float | None) -> str:
    values = [_number(sample.get(key)) for sample in samples if sample.get(key) is not None]
    if not values:
        return '<div class="e2sg-spark-empty"></div>'
    if len(values) == 1:
        values = [values[0], values[0]]
    if len(values) <= 2 or max(values) == min(values):
        positions = [15.0] * len(values)
    else:
        maximum = ceiling or max(values) or 1
        positions = [26 - min(value / maximum, 1) * 22 for value in values]
    points = " ".join(
        f"{index * 120 / (len(positions) - 1):.2f},{position:.2f}"
        for index, position in enumerate(positions)
    )
    return (
        '<svg class="e2sg-sparkline" viewBox="0 0 120 28" preserveAspectRatio="none" '
        f'role="img" aria-label="{html.escape(label_for_key(key))} over time">'
        '<path d="M0 26H120" class="e2sg-spark-grid"/>'
        f'<polyline points="{points}"/></svg>'
    )


def label_for_key(key: str) -> str:
    return key.replace("_", " ")


def _cell_timings(result: RunResult, source: Path) -> str:
    event_durations: dict[int, float] = {}
    for event in result.events:
        cell_number = event.get("cell")
        if isinstance(cell_number, (int, str)) and event.get("duration") is not None:
            event_durations[int(cell_number)] = _number(event.get("duration"))
    rows: list[tuple[str, float]] = []
    section = "Setup"
    for cell in cells(source):
        if cell.kind == "markdown":
            headings = [
                line.lstrip("# ").strip()
                for line in markdown(cell.source, source).splitlines()
                if line.startswith("#")
            ]
            if headings:
                section = headings[-1]
        elif cell.index in event_durations:
            rows.append((section, event_durations[cell.index]))
    if not rows:
        return ""
    maximum = max(duration for _, duration in rows) or 1
    content = "".join(
        '<div class="e2sg-timing-row">'
        f'<span class="e2sg-timing-label">{html.escape(label)}</span>'
        '<span class="e2sg-timing-track"><span class="e2sg-timing-bar" '
        f'style="width:{max(1.5, duration / maximum * 100):.2f}%"></span></span>'
        f"<strong>{_duration(duration)}</strong></div>"
        for label, duration in rows
    )
    return (
        '<div class="e2sg-timings"><h3 class="e2sg-telemetry-subtitle">Cell timings</h3>'
        f"{content}</div>"
    )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _gpu_models(gpus: list[dict[str, Any]]) -> str:
    if not gpus:
        return "Not detected"
    return "; ".join(
        f"{gpu.get('name', 'Unknown')} · {_megabytes(gpu.get('memory_total_mb'))}" for gpu in gpus
    )


def _gpu_software(gpus: list[dict[str, Any]]) -> str:
    if not gpus:
        return "Not available"
    drivers = sorted({str(gpu.get("driver", "Unknown")) for gpu in gpus})
    cuda_versions = sorted({str(gpu["cuda_version"]) for gpu in gpus if gpu.get("cuda_version")})
    cuda = ", ".join(cuda_versions) if cuda_versions else "unavailable"
    return f"Driver {', '.join(drivers)} · CUDA support {cuda}"


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _duration(value: object) -> str:
    seconds = _number(value)
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    return f"{int(seconds // 60)}m {seconds % 60:.0f}s"


def _percent(value: object) -> str:
    return "–" if value is None else f"{_number(value):.0f}%"


def _megabytes(value: object) -> str:
    amount = _number(value)
    return "–" if not amount else f"{amount / 1024:.1f} GiB"


def _watts(value: object) -> str:
    return "n/a" if value is None else f"{_number(value):.0f} W"


def _bytes(value: object) -> str:
    amount = _number(value)
    if not amount:
        return "–"
    if amount >= 1024**3:
        return f"{amount / 1024**3:.1f} GiB"
    return f"{amount / 1024**2:.0f} MiB"
