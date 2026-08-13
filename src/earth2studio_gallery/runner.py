from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, ImageOps

from .config import ExampleConfig, GalleryConfig
from .discovery import Example
from .progress import ProgressCallback, report
from .telemetry import TelemetrySampler

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


@dataclass(slots=True)
class RunResult:
    fingerprint: str
    duration: float
    returncode: int
    cached: bool
    events: list[dict[str, object]]
    artifacts: list[str]
    error: str | None = None
    telemetry: dict[str, object] = field(default_factory=dict)
    environment: dict[str, object] = field(default_factory=dict)
    stale: bool = False


@dataclass(frozen=True, slots=True)
class _ScriptEnvironment:
    """Execution environment selected by an example's inline metadata."""

    mode: str = "isolated"
    extras: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()


def fingerprint(example: Example, config: ExampleConfig, project_root: Path | None = None) -> str:
    digest = hashlib.blake2b(digest_size=20)
    digest.update(example.source.read_bytes())
    digest.update(json.dumps(asdict(config), sort_keys=True).encode())
    if project_root is not None:
        metadata = _script_metadata(example.source, project_root)
        try:
            environment = _script_environment(metadata, project_root, config)
        except ValueError:
            environment = _ScriptEnvironment()
        if environment.mode == "project":
            lockfile = project_root / "uv.lock"
            digest.update(lockfile.read_bytes() if lockfile.exists() else b"missing-uv-lock")
    digest.update(b"earth2studio-gallery-runner-v6")
    return digest.hexdigest()


def run_example(
    example: Example,
    gallery: GalleryConfig,
    *,
    force: bool = False,
    progress: ProgressCallback | None = None,
) -> RunResult:
    name = example.relative.as_posix()
    run_config = gallery.example_config(example.source)
    metadata = _script_metadata(example.source, gallery.root)
    metadata_error: str | None = None
    try:
        script_environment = _script_environment(metadata, gallery.root, run_config)
    except ValueError as exc:
        script_environment = _ScriptEnvironment(
            run_config.environment, run_config.extras, run_config.groups
        )
        metadata_error = str(exc)
    report(progress, "cache", "checking source and runner fingerprint", name)
    key = fingerprint(example, run_config, gallery.root)
    run_dir = gallery.cache_dir / "runs" / example.slug
    manifest_path = run_dir / "manifest.json"
    if not force and manifest_path.exists():
        cached = _read_result(manifest_path)
        telemetry_available = not gallery.collect_telemetry or bool(cached.telemetry)
        environment_available = bool(cached.environment)
        if (
            cached.fingerprint == key
            and cached.returncode == 0
            and telemetry_available
            and environment_available
        ):
            cached.cached = True
            report(progress, "cache", f"hit; reusing {len(cached.artifacts)} artifact(s)", name)
            return cached

    if run_dir.exists():
        shutil.rmtree(run_dir)
    work_dir = run_dir / "work"
    artifact_dir = run_dir / "artifacts"
    work_dir.mkdir(parents=True)
    artifact_dir.mkdir()
    event_path = run_dir / "events.json"
    environment_path = run_dir / "environment.json"
    harness_path = run_dir / "harness.py"
    report(
        progress,
        "prepare",
        f"creating {script_environment.mode} execution harness",
        name,
    )
    harness_path.write_text(
        metadata
        + "\n"
        + _HARNESS.replace("__SOURCE__", repr(str(example.source)))
        .replace("__EVENTS__", repr(str(event_path)))
        .replace("__ENVIRONMENT__", repr(str(environment_path))),
        encoding="utf-8",
    )
    process_environment = gallery.environment(run_config)
    command = _execution_command(harness_path, gallery.root, run_config, script_environment)
    preparation_error = metadata_error
    if script_environment.mode == "project" and preparation_error is None:
        details = _project_environment_details(script_environment)
        report(progress, "environment", f"reusing project environment{details}", name)
        preparation_error = _validate_project_environment(
            gallery.root, script_environment, process_environment
        )
        if preparation_error is None:
            report(progress, "lock", "verified local uv.lock", name)
    started = time.monotonic()
    sampler = TelemetrySampler(gallery.collect_telemetry, gallery.telemetry_interval)
    error: str | None = None
    if preparation_error is not None:
        returncode, error = 2, preparation_error
    else:
        action = (
            "reusing project environment without syncing"
            if script_environment.mode == "project"
            else "UV resolving isolated environment and running"
        )
        report(
            progress,
            "execute",
            f"{action} (timeout {run_config.timeout}s)",
            name,
        )
        try:
            process = subprocess.Popen(
                command,
                cwd=work_dir,
                env=process_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            sampler.sample(process, started, force=True)
            stdout, stderr, timed_out = _communicate_with_heartbeats(
                process, run_config.timeout, started, progress, name, sampler
            )
            sampler.sample(process, started, force=True)
            returncode = 124 if timed_out else process.returncode
            if timed_out:
                error = (
                    f"example timed out after {run_config.timeout}s\n"
                    f"{(stderr or stdout)[-8000:]}"
                )
            elif returncode:
                error = (stderr or stdout)[-8000:]
        except FileNotFoundError:
            returncode, error = 127, "uv was not found on PATH"
    duration = time.monotonic() - started
    if returncode:
        report(progress, "failed", f"execution exited {returncode} after {duration:.1f}s", name)
    else:
        report(progress, "execute", f"completed in {duration:.1f}s", name)
    events = json.loads(event_path.read_text(encoding="utf-8")) if event_path.exists() else []
    environment = _environment_provenance(
        environment_path,
        gallery,
        metadata,
        command,
        harness_path,
        script_environment,
    )
    environment_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")
    packages = environment.get("packages", [])
    package_count = len(packages) if isinstance(packages, list) else 0
    report(progress, "environment", f"captured {package_count} installed package(s)", name)
    report(progress, "capture", "collecting images and cell output", name)
    images = _collect_images(work_dir, events, artifact_dir)
    report(progress, "capture", f"collected {len(images)} image artifact(s)", name)
    telemetry = sampler.result(duration, events)
    if telemetry:
        report(progress, "telemetry", f"recorded {len(sampler.samples)} resource sample(s)", name)
    result = RunResult(
        key,
        duration,
        returncode,
        False,
        events,
        images,
        error,
        telemetry,
        environment,
    )
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result


def _communicate_with_heartbeats(
    process: subprocess.Popen[str],
    timeout: int,
    started: float,
    progress: ProgressCallback | None,
    name: str,
    sampler: TelemetrySampler,
) -> tuple[str, str, bool]:
    deadline = started + timeout
    next_heartbeat = 30.0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            stdout, stderr = process.communicate()
            return stdout, stderr, True
        try:
            stdout, stderr = process.communicate(timeout=min(sampler.poll_interval, remaining))
            return stdout, stderr, False
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - started
            sampler.observe_cpu(process, started)
            sampler.sample(process, started)
            if elapsed >= next_heartbeat:
                report(progress, "execute", f"still running ({elapsed:.0f}s elapsed)", name)
                next_heartbeat += 30.0


def _execution_command(
    harness: Path,
    project_root: Path,
    config: ExampleConfig,
    environment: _ScriptEnvironment,
) -> list[str]:
    if environment.mode == "project":
        return [
            "uv",
            "run",
            *config.uv_args,
            "--project",
            str(project_root),
            "--no-sync",
            "--",
            "python",
            str(harness),
        ]
    command = ["uv", "run", *config.uv_args]
    if config.python:
        command += ["--python", config.python]
    for dependency in config.extra_dependencies:
        command += ["--with", dependency]
    return [*command, "--script", str(harness)]


def _project_environment_details(environment: _ScriptEnvironment) -> str:
    selections = []
    if environment.extras:
        selections.append(f"extras: {', '.join(environment.extras)}")
    if environment.groups:
        selections.append(f"groups: {', '.join(environment.groups)}")
    return f" ({'; '.join(selections)})" if selections else ""


def _validate_project_environment(
    root: Path, environment: _ScriptEnvironment, process_environment: dict[str, str]
) -> str | None:
    pyproject = root / "pyproject.toml"
    lockfile = root / "uv.lock"
    if not pyproject.exists():
        return "project environment mode requires pyproject.toml at the gallery root"
    if not lockfile.exists():
        return "project environment mode requires uv.lock at the gallery root"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return f"could not read project metadata: {exc}"
    optional = project.get("project", {}).get("optional-dependencies", {})
    dependency_groups = project.get("dependency-groups", {})
    available_extras = set(optional) if isinstance(optional, dict) else set()
    available_groups = set(dependency_groups) if isinstance(dependency_groups, dict) else set()
    unknown_extras = sorted(set(environment.extras) - available_extras)
    unknown_groups = sorted(set(environment.groups) - available_groups)
    if unknown_extras:
        return f"unknown project extra(s): {', '.join(unknown_extras)}"
    if unknown_groups:
        return f"unknown project dependency group(s): {', '.join(unknown_groups)}"
    try:
        check = subprocess.run(
            ["uv", "lock", "--check"],
            cwd=root,
            env=process_environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return "uv was not found on PATH"
    except subprocess.TimeoutExpired:
        return "timed out while checking the project lockfile"
    if check.returncode:
        reason = (check.stderr or check.stdout).strip()
        return f"project lockfile check failed: {reason or 'uv lock --check exited nonzero'}"
    return None


def cached_result(example: Example, gallery: GalleryConfig) -> RunResult | None:
    """Return a successful retained run without executing the example."""
    manifest = gallery.cache_dir / "runs" / example.slug / "manifest.json"
    if not manifest.exists():
        return None
    result = _read_result(manifest)
    if result.returncode != 0:
        return None
    result.cached = True
    result.stale = result.fingerprint != fingerprint(
        example, gallery.example_config(example.source), gallery.root
    )
    return result


def _collect_images(work: Path, events: list[dict[str, object]], destination: Path) -> list[str]:
    discovered: dict[str, int] = {}
    for event in events:
        images = event.get("images")
        cell = event.get("cell", -1)
        cell_number = int(cell) if isinstance(cell, (int, str)) else -1
        if isinstance(images, list):
            for item in images:
                discovered[str(item)] = cell_number
    for item in work.rglob("*"):
        if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES:
            discovered.setdefault(str(item.relative_to(work)), -1)
    artifacts: list[str] = []
    for number, (relative, cell) in enumerate(discovered.items(), 1):
        source = work / relative
        if not source.exists():
            continue
        name = f"{number:03d}-cell-{cell}{source.suffix.lower()}"
        shutil.copy2(source, destination / name)
        artifacts.append(name)
    if artifacts:
        _thumbnail(destination / artifacts[0], destination / "thumbnail.webp")
    return artifacts


def _thumbnail(source: Path, destination: Path) -> None:
    if source.suffix.lower() == ".svg":
        return
    with Image.open(source) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGB")
        normalized.thumbnail((720, 480), Image.Resampling.LANCZOS, reducing_gap=3.0)
        canvas = Image.new("RGB", (720, 480), "white")
        canvas.paste(
            normalized,
            ((720 - normalized.width) // 2, (480 - normalized.height) // 2),
        )
        canvas.save(destination, "WEBP", quality=82, method=4)


def _script_metadata(source: Path, project_root: Path | None = None) -> str:
    lines = source.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "# /// script"), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "# ///"), None)
        if end is not None:
            metadata = "\n".join(lines[start : end + 1])
            return _use_local_project(metadata, source, project_root)
    return '# /// script\n# requires-python = ">=3.11"\n# dependencies = []\n# ///'


def _use_local_project(metadata: str, source: Path, project_root: Path | None) -> str:
    """Use the current checkout for a self-hosting Git dependency."""
    if project_root is None or not source.is_relative_to(project_root):
        return metadata
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return metadata
    project_name = _project_name(project_root)
    if project_name is None:
        return metadata
    git_dependency = re.compile(
        r'(?P<quote>["\'])(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)'
        r'(?P<extras>\[[^"\']+\])?\s*@\s*git\+[^"\']+(?P=quote)'
    )

    def replace(match: re.Match[str]) -> str:
        if _normalized_name(match.group("name")) != _normalized_name(project_name):
            return match.group(0)
        extras = match.group("extras") or ""
        return json.dumps(f"{match.group('name')}{extras} @ {project_root.as_uri()}")

    return git_dependency.sub(replace, metadata)


def _script_environment(
    metadata: str, project_root: Path, config: ExampleConfig
) -> _ScriptEnvironment:
    parsed = _metadata_mapping(metadata)
    tool = parsed.get("tool", {})
    if not isinstance(tool, dict):
        raise ValueError("inline script metadata [tool] must be a table")
    settings = tool.get("earth2studio-gallery", {})
    if not isinstance(settings, dict):
        raise ValueError("[tool.earth2studio-gallery] must be a table")
    mode = settings.get("environment", config.environment)
    if not isinstance(mode, str) or mode not in {"isolated", "project"}:
        raise ValueError("example environment must be 'isolated' or 'project'")
    extras = _unique((*config.extras, *_string_list(settings.get("extras", []), "extras")))
    groups = _unique((*config.groups, *_string_list(settings.get("groups", []), "groups")))
    if mode == "project":
        extras = _unique((*_project_extras(parsed, project_root), *extras))
        return _ScriptEnvironment(mode, extras, groups)
    return _ScriptEnvironment(mode)


def _project_extras(metadata: dict[str, object], project_root: Path) -> tuple[str, ...]:
    project_name = _project_name(project_root)
    dependencies = metadata.get("dependencies", [])
    if project_name is None or not isinstance(dependencies, list):
        return ()
    extras: list[str] = []
    requirement = re.compile(
        r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)" r"(?:\[(?P<extras>[^]]+)\])?"
    )
    for dependency in dependencies:
        if not isinstance(dependency, str) or not (match := requirement.match(dependency)):
            continue
        if _normalized_name(match.group("name")) != _normalized_name(project_name):
            continue
        if declared := match.group("extras"):
            extras.extend(item.strip() for item in declared.split(",") if item.strip())
    return _unique(extras)


def _project_name(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    name = data.get("project", {}).get("name")
    return name if isinstance(name, str) else None


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"project environment {name} must be an array of strings")
    return _unique(value)


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _read_result(path: Path) -> RunResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    environment = payload.get("environment")
    if isinstance(environment, dict) and "environment_variables" in environment:
        environment.pop("environment_variables")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _scrub_environment_snapshot(path.with_name("environment.json"))
    return RunResult(**payload)


def _scrub_environment_snapshot(path: Path) -> None:
    if not path.exists():
        return
    try:
        environment = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(environment, dict) or "environment_variables" not in environment:
        return
    environment.pop("environment_variables")
    path.write_text(json.dumps(environment, indent=2), encoding="utf-8")


def _environment_provenance(
    path: Path,
    gallery: GalleryConfig,
    metadata: str,
    command: list[str],
    harness_path: Path,
    script_environment: _ScriptEnvironment,
) -> dict[str, object]:
    captured: dict[str, object] = {}
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                captured = value
        except (OSError, json.JSONDecodeError):
            pass
    captured["uv"] = {
        "version": _uv_version(),
        "command": _sanitize_command(command, harness_path),
    }
    captured["execution"] = {
        "environment": script_environment.mode,
        "extras": list(script_environment.extras),
        "groups": list(script_environment.groups),
    }
    captured["script"] = _metadata_mapping(metadata)
    captured["repository"] = _repository_information(gallery.root)
    captured["project_lock"] = _lock_information(
        gallery.root / "uv.lock",
        used_by_script_environment=script_environment.mode == "project",
    )
    return captured


def _uv_version() -> str | None:
    try:
        result = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _metadata_mapping(metadata: str) -> dict[str, object]:
    content = "\n".join(
        line.removeprefix("# ").removeprefix("#")
        for line in metadata.splitlines()
        if line.strip() not in {"# /// script", "# ///"}
    )
    try:
        return tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return {}


def _sanitize_command(command: list[str], harness_path: Path) -> list[str]:
    sanitized: list[str] = []
    redact_next = False
    for value in command:
        if redact_next:
            sanitized.append("<redacted>")
            redact_next = False
            continue
        if value == str(harness_path):
            sanitized.append("<generated-harness>")
            continue
        lowered = value.lower().replace("_", "-")
        if any(word in lowered for word in ("token", "password", "credential")):
            if "=" in value:
                sanitized.append(value.split("=", 1)[0] + "=<redacted>")
            else:
                sanitized.append(value)
                redact_next = True
            continue
        sanitized.append(_sanitize_url(value))
    return sanitized


def _sanitize_url(value: str) -> str:
    if "://" not in value:
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    netloc = f"<redacted>@{hostname}" if parsed.username else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _repository_information(root: Path) -> dict[str, object]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if commit.returncode:
        return {}
    return {
        "commit": commit.stdout.strip(),
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _lock_information(path: Path, *, used_by_script_environment: bool = False) -> dict[str, object]:
    if not path.exists():
        return {
            "present": False,
            "used_by_script_environment": used_by_script_environment,
        }
    return {
        "present": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "used_by_script_environment": used_by_script_environment,
    }


_HARNESS = r"""
from __future__ import annotations
import contextlib, importlib.metadata, io, json, os, pathlib, platform, re, sys, time, traceback
from urllib.parse import urlsplit, urlunsplit

SOURCE = pathlib.Path(__SOURCE__)
EVENTS = pathlib.Path(__EVENTS__)
ENVIRONMENT = pathlib.Path(__ENVIRONMENT__)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}

def safe_url(value):
    if "://" not in value:
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    netloc = f"<redacted>@{hostname}" if parsed.username else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

def package_source(distribution):
    try:
        content = distribution.read_text("direct_url.json")
        direct = json.loads(content) if content else {}
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(direct, dict):
        return None
    url = str(direct.get("url", ""))
    vcs = direct.get("vcs_info")
    if isinstance(vcs, dict):
        return {
            "type": str(vcs.get("vcs", "vcs")),
            "url": safe_url(url),
            "commit": vcs.get("commit_id"),
            "requested_revision": vcs.get("requested_revision"),
        }
    if url.startswith("file:"):
        directory = direct.get("dir_info")
        return {
            "type": "local",
            "editable": bool(directory.get("editable")) if isinstance(directory, dict) else False,
        }
    return {"type": "archive", "url": safe_url(url)} if url else None

def environment_snapshot():
    packages = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name") or distribution.name
        package = {"name": str(name), "version": distribution.version}
        source = package_source(distribution)
        if source:
            package["source"] = source
        packages.append(package)
    packages.sort(key=lambda item: item["name"].lower())
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "build": sys.version,
            "executable": pathlib.Path(sys.executable).name,
            "uv_environment": pathlib.Path(sys.prefix).name,
            "platform": platform.platform(),
        },
        "packages": packages,
    }

ENVIRONMENT.write_text(json.dumps(environment_snapshot(), indent=2), encoding="utf-8")

def split_cells(text):
    marker = re.compile(r"^#\s*%%.*$", re.MULTILINE)
    profile = re.compile(r"['\"]e2sg-profile:([A-Za-z0-9_-]+)['\"]")
    matches = list(marker.finditer(text))
    chunks = []
    for number, match in enumerate(matches):
        start = match.end() + (1 if text[match.end():].startswith("\n") else 0)
        end = matches[number + 1].start() if number + 1 < len(matches) else len(text)
        tagged = profile.search(match.group(0))
        chunks.append((text[start:end], tagged.group(1) if tagged else None))
    return chunks or [(text, None)]

def files():
    return {str(p.relative_to(pathlib.Path.cwd())): (p.stat().st_mtime_ns, p.stat().st_size)
            for p in pathlib.Path.cwd().rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}

class CapturedStream:
    def __init__(self, stream, combined):
        self.stream = stream
        self.combined = combined
        self.encoding = "utf-8"

    def write(self, value):
        self.stream.write(value)
        self.combined.write(value)
        return len(value)

    def flush(self):
        return None

    def isatty(self):
        return False

namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
events = []
failed = False
for index, (cell, region) in enumerate(split_cells(SOURCE.read_text(encoding="utf-8"))):
    try:
        tree = compile(cell, str(SOURCE), "exec", flags=0, dont_inherit=True)
    except (SyntaxError, ValueError):
        continue
    before = files()
    stdout, stderr, output = io.StringIO(), io.StringIO(), io.StringIO()
    event = {
        "cell": index,
        "stdout": "",
        "stderr": "",
        "output": "",
        "failed": False,
        "images": [],
        "duration": 0.0,
        "region": region,
        "started_at": 0.0,
        "ended_at": 0.0,
    }
    event["started_at"] = time.time()
    cell_started = time.perf_counter()
    try:
        with contextlib.redirect_stdout(CapturedStream(stdout, output)):
            with contextlib.redirect_stderr(CapturedStream(stderr, output)):
                exec(tree, namespace)
    except Exception:
        formatted = traceback.format_exc()
        stderr.write(formatted)
        output.write(formatted)
        event["failed"] = True
        failed = True
    event["duration"] = time.perf_counter() - cell_started
    event["ended_at"] = time.time()
    event["stdout"], event["stderr"] = stdout.getvalue(), stderr.getvalue()
    event["output"] = output.getvalue()
    after = files()
    event["images"] = [name for name, signature in after.items() if before.get(name) != signature]
    if not event["images"]:
        try:
            import matplotlib.pyplot as plt
            for figure_number in plt.get_fignums():
                name = f"gallery-auto-{index:03d}-{figure_number}.png"
                plt.figure(figure_number).savefig(name, bbox_inches="tight")
                event["images"].append(name)
            plt.close("all")
        except ImportError:
            pass
    events.append(event)
    if failed:
        break
EVENTS.write_text(json.dumps(events, indent=2), encoding="utf-8")
if failed:
    raise SystemExit(1)
"""
