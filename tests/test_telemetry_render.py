from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import earth2studio_gallery.telemetry as telemetry
from earth2studio_gallery.runner import RunResult
from earth2studio_gallery.telemetry import (
    TelemetrySampler,
    _cuda_version_from_output,
    _region_summaries,
)
from earth2studio_gallery.telemetry_render import _sparkline, telemetry_panel


def test_sparse_sparklines_share_the_same_midline() -> None:
    samples = [{"value": 47.5}, {"value": 48.2}]

    chart = _sparkline(samples, "value", ceiling=100.0)

    assert 'points="0.00,15.00 120.00,15.00"' in chart


def test_parses_driver_supported_cuda_version() -> None:
    output = "NVIDIA-SMI 610.57.04    Driver Version: 610.57.04    CUDA Version: 13.1"

    assert _cuda_version_from_output(output) == "13.1"

    output = "NVIDIA-SMI 610.57.04    KMD Version: 610.57.04    CUDA UMD Version: 13.3"

    assert _cuda_version_from_output(output) == "13.3"


def test_cpu_usage_uses_cpu_time_instead_of_first_cpu_percent_call(monkeypatch: Any) -> None:
    cpu_seconds = iter([0.0, 0.08])
    process = SimpleNamespace(
        pid=7,
        create_time=lambda: 1.0,
        cpu_times=lambda: SimpleNamespace(user=next(cpu_seconds), system=0.0),
    )
    monotonic = iter([0.0, 0.1])
    monkeypatch.setattr(telemetry, "_system_information", lambda: {})
    monkeypatch.setattr(telemetry, "_gpu_information", lambda: [])
    monkeypatch.setattr(telemetry, "_process_tree", lambda _pid: [process])
    monkeypatch.setattr(telemetry.time, "monotonic", lambda: next(monotonic))
    sampler = TelemetrySampler(True)
    popen = cast(Any, SimpleNamespace(pid=7))

    sampler.observe_cpu(popen, 0.0, force=True)
    sampler.observe_cpu(popen, 0.0, force=True)
    result = sampler.result(0.2)
    summary = cast("dict[str, float]", result["summary"])

    assert summary["average_cpu_percent"] == 40.0
    assert summary["peak_cpu_percent"] == 80.0


def test_region_summaries_filter_samples_and_measure_network_delta() -> None:
    samples = [
        {
            "timestamp": 9.0,
            "gpu_percent": 0.0,
            "network_received_bytes": 100.0,
            "network_sent_bytes": 40.0,
        },
        {
            "timestamp": 11.0,
            "gpu_percent": 75.0,
            "network_received_bytes": 500.0,
            "network_sent_bytes": 90.0,
        },
        {
            "timestamp": 13.0,
            "gpu_percent": 0.0,
            "network_received_bytes": 700.0,
            "network_sent_bytes": 100.0,
        },
    ]
    events = [
        {
            "region": "inference",
            "started_at": 10.0,
            "ended_at": 12.0,
        }
    ]

    region = _region_summaries(samples, events)[0]

    assert region["name"] == "inference"
    assert region["sample_count"] == 1
    assert region["average_gpu_percent"] == 75.0
    assert region["network_received_bytes"] == 600.0
    assert region["network_sent_bytes"] == 60.0


def test_untagged_run_has_no_metric_grid() -> None:
    result = RunResult(
        "fingerprint",
        1.25,
        0,
        False,
        [],
        [],
        telemetry={
            "summary": {"duration_seconds": 1.25, "average_cpu_percent": 75.0},
            "system": {},
            "gpus": [],
            "samples": [{"cpu_percent": 75.0}],
            "regions": [],
        },
    )

    panel = telemetry_panel(result, Path("example.py"))

    assert 'class="e2sg-metric-grid"' not in panel
    assert "Total runtime" in panel
    assert "1.2 s" in panel
