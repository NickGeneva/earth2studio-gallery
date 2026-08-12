from __future__ import annotations

import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil


class TelemetrySampler:
    def __init__(self, enabled: bool, interval: float = 1.0):
        self.enabled = enabled
        self.interval = max(0.25, interval)
        self.poll_interval = min(0.1, self.interval) if enabled else self.interval
        self.last_sample = 0.0
        self.samples: list[dict[str, float]] = []
        self.system = _system_information() if enabled else {}
        self.gpus = _gpu_information() if enabled else []
        self._last_cpu_observation: float | None = None
        self._cpu_totals: dict[tuple[int, float], float] = {}
        self._root_cpu_seconds = 0.0
        self._cpu_percent = 0.0
        self._peak_cpu_percent = 0.0
        self._cpu_observed = False
        self._network_start = _network_counters() if enabled else None

    def observe_cpu(
        self, process: subprocess.Popen[str], started: float, *, force: bool = False
    ) -> None:
        """Measure process-tree CPU from cumulative times without psutil's first-call zero."""
        if not self.enabled:
            return
        now = time.monotonic()
        if (
            not force
            and self._last_cpu_observation is not None
            and now - self._last_cpu_observation < self.poll_interval
        ):
            return
        previous_observation = self._last_cpu_observation or started
        cpu_delta = 0.0
        for item in _process_tree(process.pid):
            try:
                key = (item.pid, item.create_time())
                times = item.cpu_times()
                total = float(times.user + times.system)
            except (psutil.Error, OSError):
                continue
            previous = self._cpu_totals.get(key, 0.0)
            if total >= previous:
                cpu_delta += total - previous
                self._cpu_totals[key] = total
            if item.pid == process.pid:
                inclusive = total + float(
                    getattr(times, "children_user", 0.0) + getattr(times, "children_system", 0.0)
                )
                self._root_cpu_seconds = max(self._root_cpu_seconds, inclusive)
            self._cpu_observed = True
        elapsed = now - previous_observation
        if elapsed > 0:
            self._cpu_percent = cpu_delta / elapsed * 100
            self._peak_cpu_percent = max(self._peak_cpu_percent, self._cpu_percent)
        self._last_cpu_observation = now

    def sample(
        self, process: subprocess.Popen[str], started: float, *, force: bool = False
    ) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now - self.last_sample < self.interval:
            return
        self.last_sample = now
        self.observe_cpu(process, started, force=force)
        sample: dict[str, float] = {
            "time": round(now - started, 3),
            "timestamp": time.time(),
        }
        try:
            parent = psutil.Process(process.pid)
            processes = [parent, *parent.children(recursive=True)]
            sample["rss_bytes"] = float(
                sum(item.memory_info().rss for item in processes if item.is_running())
            )
        except (psutil.Error, OSError):
            pass
        gpu_sample = _gpu_sample()
        if gpu_sample:
            sample.update(gpu_sample)
        network = _network_counters()
        if self._network_start is not None and network is not None:
            sample["network_received_bytes"] = float(
                max(0, network.bytes_recv - self._network_start.bytes_recv)
            )
            sample["network_sent_bytes"] = float(
                max(0, network.bytes_sent - self._network_start.bytes_sent)
            )
        # GPU queries can outlive a short example. Observe once more before the
        # caller reaps the process so its final cumulative CPU time is retained.
        self.observe_cpu(process, started, force=True)
        if self._cpu_observed:
            sample["cpu_percent"] = self._cpu_percent
        self.samples.append(sample)

    def result(
        self, duration: float, events: list[dict[str, object]] | None = None
    ) -> dict[str, object]:
        if not self.enabled:
            return {}
        total_cpu_seconds = max(sum(self._cpu_totals.values()), self._root_cpu_seconds)
        average_cpu_percent = (
            total_cpu_seconds / duration * 100 if self._cpu_observed and duration > 0 else None
        )
        return {
            "system": self.system,
            "gpus": self.gpus,
            "summary": {
                "duration_seconds": round(duration, 3),
                "peak_rss_bytes": _maximum(self.samples, "rss_bytes"),
                "average_cpu_percent": _rounded(average_cpu_percent),
                "peak_cpu_percent": (
                    round(self._peak_cpu_percent, 3) if self._cpu_observed else None
                ),
                "average_gpu_percent": _average(self.samples, "gpu_percent"),
                "peak_gpu_percent": _maximum(self.samples, "gpu_percent"),
                "peak_gpu_memory_mb": _maximum(self.samples, "gpu_memory_mb"),
                "peak_gpu_power_watts": _maximum(self.samples, "gpu_power_watts"),
                "network_received_bytes": _maximum(self.samples, "network_received_bytes"),
                "network_sent_bytes": _maximum(self.samples, "network_sent_bytes"),
            },
            "samples": self.samples,
            "regions": _region_summaries(self.samples, events or []),
        }


def _process_tree(pid: int) -> list[psutil.Process]:
    try:
        parent = psutil.Process(pid)
    except (psutil.Error, OSError):
        return []
    try:
        return [parent, *parent.children(recursive=True)]
    except (psutil.Error, OSError):
        return [parent]


def _network_counters() -> Any | None:
    try:
        return psutil.net_io_counters()
    except (psutil.Error, OSError):
        return None


def _region_summaries(
    samples: list[dict[str, float]], events: list[dict[str, object]]
) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[float, float]]] = {}
    for event in events:
        region = event.get("region")
        started = event.get("started_at")
        ended = event.get("ended_at")
        if not isinstance(region, str) or not region:
            continue
        if not isinstance(started, (int, float)) or not isinstance(ended, (int, float)):
            continue
        grouped.setdefault(region, []).append((float(started), float(ended)))
    regions: list[dict[str, object]] = []
    for name, intervals in grouped.items():
        selected = [
            sample
            for sample in samples
            if any(start <= sample.get("timestamp", 0.0) <= end for start, end in intervals)
        ]
        regions.append(
            {
                "name": name,
                "duration_seconds": round(sum(end - start for start, end in intervals), 3),
                "sample_count": len(selected),
                "average_cpu_percent": _average(selected, "cpu_percent"),
                "peak_cpu_percent": _maximum(selected, "cpu_percent"),
                "peak_rss_bytes": _maximum(selected, "rss_bytes"),
                "average_gpu_percent": _average(selected, "gpu_percent"),
                "peak_gpu_percent": _maximum(selected, "gpu_percent"),
                "peak_gpu_memory_mb": _maximum(selected, "gpu_memory_mb"),
                "peak_gpu_power_watts": _maximum(selected, "gpu_power_watts"),
                "network_received_bytes": _region_counter_delta(
                    samples, intervals, "network_received_bytes"
                ),
                "network_sent_bytes": _region_counter_delta(
                    samples, intervals, "network_sent_bytes"
                ),
                "samples": selected,
            }
        )
    return regions


def _region_counter_delta(
    samples: list[dict[str, float]], intervals: list[tuple[float, float]], key: str
) -> float | None:
    available = [sample for sample in samples if key in sample and "timestamp" in sample]
    if not available:
        return None
    total = 0.0
    for start, end in intervals:
        before = [sample for sample in available if sample["timestamp"] <= start]
        after = [sample for sample in available if sample["timestamp"] >= end]
        first = before[-1] if before else available[0]
        last = after[0] if after else available[-1]
        total += max(0.0, last[key] - first[key])
    return round(total, 3)


def _system_information() -> dict[str, object]:
    memory = psutil.virtual_memory()
    return {
        "cpu": _cpu_name(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_total_bytes": memory.total,
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }


def _cpu_name() -> str:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def _nvidia_smi(fields: str) -> list[list[str]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={fields}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    return [[value.strip() for value in line.split(",")] for line in result.stdout.splitlines()]


def _gpu_information() -> list[dict[str, object]]:
    rows = _nvidia_smi("index,name,driver_version,memory.total")
    cuda_version = _cuda_version()
    return [
        {
            "index": _number(row[0]),
            "name": row[1],
            "driver": row[2],
            "cuda_version": cuda_version,
            "memory_total_mb": _number(row[3]),
        }
        for row in rows
        if len(row) >= 4
    ]


def _cuda_version() -> str | None:
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return _cuda_version_from_output(result.stdout) if result.returncode == 0 else None


def _cuda_version_from_output(output: str) -> str | None:
    match = re.search(r"CUDA(?: UMD)? Version:\s*([0-9.]+)", output)
    return match.group(1) if match else None


def _gpu_sample() -> dict[str, float]:
    rows = _nvidia_smi("utilization.gpu,memory.used,power.draw")
    parsed = [row for row in rows if len(row) >= 3]
    if not parsed:
        return {}
    return {
        "gpu_percent": max(_number(row[0]) for row in parsed),
        "gpu_memory_mb": sum(_number(row[1]) for row in parsed),
        "gpu_power_watts": sum(_number(row[2]) for row in parsed),
    }


def _number(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def _values(samples: list[dict[str, float]], key: str) -> list[float]:
    return [sample[key] for sample in samples if key in sample]


def _maximum(samples: list[dict[str, float]], key: str) -> float | None:
    values = _values(samples, key)
    return round(max(values), 3) if values else None


def _average(samples: list[dict[str, float]], key: str) -> float | None:
    values = _values(samples, key)
    return round(statistics.fmean(values), 3) if values else None


def _rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None
