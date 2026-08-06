from earth2studio_gallery.telemetry import _cuda_version_from_output
from earth2studio_gallery.telemetry_render import _sparkline


def test_sparse_sparklines_share_the_same_midline() -> None:
    samples = [{"value": 47.5}, {"value": 48.2}]

    chart = _sparkline(samples, "value", ceiling=100.0)

    assert 'points="0.00,15.00 120.00,15.00"' in chart


def test_parses_driver_supported_cuda_version() -> None:
    output = "NVIDIA-SMI 610.57.04    Driver Version: 610.57.04    CUDA Version: 13.1"

    assert _cuda_version_from_output(output) == "13.1"

    output = "NVIDIA-SMI 610.57.04    KMD Version: 610.57.04    CUDA UMD Version: 13.3"

    assert _cuda_version_from_output(output) == "13.3"
