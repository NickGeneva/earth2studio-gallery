from pathlib import Path

from earth2studio_gallery.config import GalleryConfig
from earth2studio_gallery.discovery import discover

SCRIPT = '''# %%
"""An Example
=============

A summary.
"""
'''


def test_selects_one_section_or_glob(tmp_path: Path) -> None:
    for name in ("01_start/01_one.py", "01_start/02_two.py", "02_more/01_three.py"):
        path = tmp_path / "examples" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SCRIPT, encoding="utf-8")
    config = GalleryConfig.load(tmp_path)
    assert len(discover(config)) == 3
    assert len(discover(config, ["01_start"])) == 2
    assert [item.relative.as_posix() for item in discover(config, ["*three*"])] == [
        "02_more/01_three.py"
    ]
    assert len(discover(config, ["02_two"])) == 1


def test_inherits_runner_configuration(tmp_path: Path) -> None:
    example = tmp_path / "examples" / "gpu" / "run.py"
    example.parent.mkdir(parents=True)
    example.write_text(SCRIPT, encoding="utf-8")
    (tmp_path / "examples" / "_gallery.toml").write_text(
        '[runner]\ntimeout = 30\nextra_dependencies = ["base"]\n[runner.env]\nA = "1"\n',
        encoding="utf-8",
    )
    example.with_suffix(".gallery.toml").write_text(
        '[runner]\nextra_dependencies = ["extra"]\n[runner.env]\nB = "2"\n',
        encoding="utf-8",
    )
    runner = GalleryConfig.load(tmp_path).example_config(example)
    assert runner.timeout == 30
    assert runner.extra_dependencies == ("base", "extra")
    assert runner.env == {"A": "1", "B": "2"}
