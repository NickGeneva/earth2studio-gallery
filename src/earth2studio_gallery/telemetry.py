from __future__ import annotations

import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil


class TelemetrySampler:
    def __init__(self, enabled: bool, interval: float = 1.0):
        self.enabled = enabled
        self.interval = max(0.25, interval)
        self.last_sample = 0.0
        self.samples: list[dict[str, float]] = []
        self.system = _system_information() if enabled else {}
        self.gpus = _gpu_information() if enabled else []

    def sample(
        self, process: subprocess.Popen[str], started: float, *, force: bool = False
    ) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now - self.last_sample < self.interval:
            return
        self.last_sample = now
        sample: dict[str, float] = {"time": round(now - started, 3)}
        try:
            parent = psutil.Process(process.pid)
            processes = [parent, *parent.children(recursive=True)]
            sample["rss_bytes"] = float(
                sum(item.memory_info().rss for item in processes if item.is_running())
            )
            sample["cpu_percent"] = float(
                sum(item.cpu_percent(interval=None) for item in processes if item.is_running())
            )
        except (psutil.Error, OSError):
            pass
        gpu_sample = _gpu_sample()
        if gpu_sample:
            sample.update(gpu_sample)
        self.samples.append(sample)

    def result(self, duration: float) -> dict[str, object]:
        if not self.enabled:
            return {}
        return {
            "system": self.system,
            "gpus": self.gpus,
            "summary": {
                "duration_seconds": round(duration, 3),
                "peak_rss_bytes": _maximum(self.samples, "rss_bytes"),
                "average_cpu_percent": _average(self.samples, "cpu_percent"),
                "peak_cpu_percent": _maximum(self.samples, "cpu_percent"),
                "average_gpu_percent": _average(self.samples, "gpu_percent"),
                "peak_gpu_percent": _maximum(self.samples, "gpu_percent"),
                "peak_gpu_memory_mb": _maximum(self.samples, "gpu_memory_mb"),
                "peak_gpu_power_watts": _maximum(self.samples, "gpu_power_watts"),
            },
            "samples": self.samples,
        }


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
