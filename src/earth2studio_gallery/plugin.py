from __future__ import annotations

import logging
from pathlib import Path

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin

from .builder import GalleryBuilder
from .config import GalleryConfig
from .progress import ProgressEvent

log = logging.getLogger("mkdocs.plugins.earth2studio-gallery")


def _log_progress(event: ProgressEvent) -> None:
    prefix = f"{event.example}: " if event.example else ""
    log.info("%-9s %s%s", event.stage.upper(), prefix, event.message)


class GalleryPlugin(BasePlugin):
    config_scheme = (
        ("examples_dir", config_options.Type(str, default="examples")),
        ("output_dir", config_options.Type(str, default="gallery")),
        ("cache_dir", config_options.Type(str, default=".e2sgallery")),
        ("execute", config_options.Choice(("stale", "always", "never"), default="stale")),
        ("jobs", config_options.Type(int, default=1)),
        ("fail_fast", config_options.Type(bool, default=True)),
        ("optimize_images", config_options.Type(bool, default=True)),
        ("image_max_width", config_options.Type(int, default=2400)),
        ("image_max_height", config_options.Type(int, default=1600)),
        ("image_quality", config_options.Type(int, default=85)),
        ("image_min_bytes", config_options.Type(int, default=131072)),
        ("generate_notebooks", config_options.Type(bool, default=True)),
        ("backreferences", config_options.Type(bool, default=False)),
        ("output_open", config_options.Type(bool, default=False)),
        ("output_max_height", config_options.Type(int, default=400)),
        ("download_button_color", config_options.Type(str, default="")),
        ("collect_telemetry", config_options.Type(bool, default=False)),
        ("telemetry_interval", config_options.Type(float, default=1.0)),
    )

    def on_config(self, config, **kwargs):
        config_file = Path(config.config_file_path or ".").resolve()
        root = config_file.parent if config_file.is_file() else config_file
        overrides = {
            "examples_dir": self.config["examples_dir"],
            "output_dir": Path(config.docs_dir) / self.config["output_dir"],
            "cache_dir": self.config["cache_dir"],
            "execute": self.config["execute"],
            "jobs": self.config["jobs"],
            "fail_fast": self.config["fail_fast"],
            "optimize_images": self.config["optimize_images"],
            "image_max_width": self.config["image_max_width"],
            "image_max_height": self.config["image_max_height"],
            "image_quality": self.config["image_quality"],
            "image_min_bytes": self.config["image_min_bytes"],
            "generate_notebooks": self.config["generate_notebooks"],
            "backreferences": self.config["backreferences"],
            "output_open": self.config["output_open"],
            "output_max_height": self.config["output_max_height"],
            "collect_telemetry": self.config["collect_telemetry"],
            "telemetry_interval": self.config["telemetry_interval"],
        }
        if self.config["download_button_color"]:
            overrides["download_button_color"] = self.config["download_button_color"]
        gallery = GalleryConfig.load(
            root,
            docs_dir=config.docs_dir,
            overrides=overrides,
        )
        log.info("Generating Earth2Studio gallery from %s", gallery.examples_dir)
        report = GalleryBuilder(gallery, progress=_log_progress).build()
        if report.failures:
            names = ", ".join(example.relative.as_posix() for example, _ in report.failures)
            raise RuntimeError(f"Gallery examples failed: {names}")
        css = "assets/stylesheets/earth2studio-gallery.css"
        if css not in config.extra_css:
            config.extra_css.append(css)
        return config
