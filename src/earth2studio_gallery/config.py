from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExampleConfig:
    python: str | None = None
    timeout: int = 7200
    extra_dependencies: tuple[str, ...] = ()
    uv_args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    execute: bool = True
    thumbnail: str | None = None


@dataclass(frozen=True, slots=True)
class GalleryConfig:
    root: Path
    examples_dir: Path
    docs_dir: Path
    output_dir: Path
    cache_dir: Path
    execute: str = "stale"
    pattern: str = "*.py"
    jobs: int = 1
    fail_fast: bool = True
    optimize_images: bool = True
    image_max_width: int = 2400
    image_max_height: int = 1600
    image_quality: int = 85
    image_min_bytes: int = 131072
    generate_notebooks: bool = True
    backreferences: bool = False
    output_open: bool = False
    output_max_height: int = 400
    download_button_color: str | None = None
    collect_telemetry: bool = False
    telemetry_interval: float = 1.0
    default: ExampleConfig = field(default_factory=ExampleConfig)

    @classmethod
    def load(
        cls,
        root: str | Path = ".",
        *,
        examples_dir: str | Path = "examples",
        docs_dir: str | Path = "docs",
        output_dir: str | Path = "gallery",
        cache_dir: str | Path = ".e2sgallery",
        overrides: dict[str, Any] | None = None,
    ) -> GalleryConfig:
        root_path = Path(root).resolve()
        data: dict[str, Any] = {}
        pyproject = root_path / "pyproject.toml"
        gallery_toml = root_path / "gallery.toml"
        if pyproject.exists():
            raw = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            data.update(raw.get("tool", {}).get("earth2studio-gallery", {}))
        if gallery_toml.exists():
            raw = tomllib.loads(gallery_toml.read_text(encoding="utf-8"))
            data.update(raw.get("gallery", raw))
        data.update(overrides or {})

        def path_value(key: str, fallback: str | Path) -> Path:
            value = Path(data.get(key, fallback))
            return value if value.is_absolute() else root_path / value

        default_data = data.get("runner", {})
        default = ExampleConfig(
            python=default_data.get("python"),
            timeout=int(default_data.get("timeout", 7200)),
            extra_dependencies=tuple(default_data.get("extra_dependencies", ())),
            uv_args=tuple(default_data.get("uv_args", ())),
            env={str(k): str(v) for k, v in default_data.get("env", {}).items()},
        )
        return cls(
            root=root_path,
            examples_dir=path_value("examples_dir", examples_dir),
            docs_dir=path_value("docs_dir", docs_dir),
            output_dir=path_value("output_dir", Path(docs_dir) / output_dir),
            cache_dir=path_value("cache_dir", cache_dir),
            execute=str(data.get("execute", "stale")),
            pattern=str(data.get("pattern", "*.py")),
            jobs=max(1, int(data.get("jobs", 1))),
            fail_fast=bool(data.get("fail_fast", True)),
            optimize_images=bool(data.get("optimize_images", True)),
            image_max_width=max(1, int(data.get("image_max_width", 2400))),
            image_max_height=max(1, int(data.get("image_max_height", 1600))),
            image_quality=min(100, max(1, int(data.get("image_quality", 85)))),
            image_min_bytes=max(0, int(data.get("image_min_bytes", 131072))),
            generate_notebooks=bool(data.get("generate_notebooks", True)),
            backreferences=bool(data.get("backreferences", False)),
            output_open=bool(data.get("output_open", False)),
            output_max_height=max(80, int(data.get("output_max_height", 400))),
            download_button_color=(
                str(data["download_button_color"]).strip()
                if data.get("download_button_color")
                else None
            ),
            collect_telemetry=bool(data.get("collect_telemetry", False)),
            telemetry_interval=max(0.25, float(data.get("telemetry_interval", 1.0))),
            default=default,
        )

    def example_config(self, source: Path) -> ExampleConfig:
        """Merge inherited `_gallery.toml` files and a script sidecar."""
        merged: dict[str, Any] = {
            "python": self.default.python,
            "timeout": self.default.timeout,
            "extra_dependencies": list(self.default.extra_dependencies),
            "uv_args": list(self.default.uv_args),
            "env": dict(self.default.env),
            "execute": self.default.execute,
            "thumbnail": self.default.thumbnail,
        }
        candidates: list[Path] = []
        current = source.parent
        while current == self.examples_dir or self.examples_dir in current.parents:
            candidates.append(current / "_gallery.toml")
            if current == self.examples_dir:
                break
            current = current.parent
        candidates.reverse()
        candidates.append(source.with_suffix(".gallery.toml"))
        for candidate in candidates:
            if not candidate.exists():
                continue
            raw = tomllib.loads(candidate.read_text(encoding="utf-8"))
            values = raw.get("runner", raw)
            for key in ("python", "timeout", "execute", "thumbnail"):
                if key in values:
                    merged[key] = values[key]
            for key in ("extra_dependencies", "uv_args"):
                if key in values:
                    merged[key] = [*merged[key], *values[key]]
            if "env" in values:
                merged["env"].update({str(k): str(v) for k, v in values["env"].items()})
        return ExampleConfig(
            python=merged["python"],
            timeout=int(merged["timeout"]),
            extra_dependencies=tuple(merged["extra_dependencies"]),
            uv_args=tuple(merged["uv_args"]),
            env=merged["env"],
            execute=bool(merged["execute"]),
            thumbnail=merged["thumbnail"],
        )

    def environment(self, example: ExampleConfig) -> dict[str, str]:
        env = os.environ.copy()
        env.update(example.env)
        env.setdefault("MPLBACKEND", "Agg")
        return env
