from pathlib import Path

import pytest

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
    (tmp_path / "pyproject.toml").write_text(
        """[tool.earth2studio-gallery.runner]
environment = "project"
extras = ["feature"]
groups = ["docs"]
""",
        encoding="utf-8",
    )
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
    assert runner.environment == "project"
    assert runner.extras == ("feature",)
    assert runner.groups == ("docs",)
    assert runner.extra_dependencies == ("base", "extra")
    assert runner.env == {"A": "1", "B": "2"}


def test_loads_referenced_gallery_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / ".config" / "earth2studio-gallery.toml"
    config_file.parent.mkdir()
    config_file.write_text(
        """[gallery]
examples_dir = "example-sources"
output_dir = "docs/generated-examples"
jobs = 2
backreferences = true

[gallery.runner]
environment = "project"
groups = ["docs"]
timeout = 600
""",
        encoding="utf-8",
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[tool.earth2studio-gallery]
config_file = ".config/earth2studio-gallery.toml"
jobs = 3
""",
        encoding="utf-8",
    )

    config = GalleryConfig.load(tmp_path)

    assert config.examples_dir == tmp_path / "example-sources"
    assert config.output_dir == tmp_path / "docs" / "generated-examples"
    assert config.jobs == 3
    assert config.backreferences is True
    assert config.default.environment == "project"
    assert config.default.groups == ("docs",)
    assert config.default.timeout == 600

    pyproject.write_text(
        '[tool.earth2studio-gallery]\nconfig_file = "docs/missing.toml"\n',
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="docs.missing.toml"):
        GalleryConfig.load(tmp_path)
