from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

CELL = re.compile(r"^#\s*%%.*$", re.MULTILINE)
ROLE = re.compile(r":(?:py:)?(?:class|func|meth|mod|attr|data):`~?([^`]+)`")
RST_LINK = re.compile(r"`([^`<>]+?)\s*<([^<>]+)>`_")


@dataclass(frozen=True, slots=True)
class Cell:
    index: int
    kind: str
    source: str
    line: int


def cells(path: Path) -> list[Cell]:
    text = path.read_text(encoding="utf-8")
    matches = list(CELL.finditer(text))
    chunks: list[tuple[str, int]] = []
    if matches and text[: matches[0].start()].strip():
        chunks.append((text[: matches[0].start()], 1))
    for number, match in enumerate(matches):
        start = match.end() + (1 if text[match.end() :].startswith("\n") else 0)
        end = matches[number + 1].start() if number + 1 < len(matches) else len(text)
        chunks.append((text[start:end], text.count("\n", 0, start) + 1))
    if not matches:
        chunks.append((text, 1))
    result: list[Cell] = []
    for source, line in chunks:
        stripped = source.strip()
        if not stripped or _is_license_preamble(stripped):
            continue
        narrative = _narrative(source)
        kind = "markdown" if narrative is not None else "code"
        result.append(
            Cell(len(result), kind, narrative if narrative is not None else source.strip(), line)
        )
    return result


def example_metadata(path: Path) -> tuple[str, str]:
    for cell in cells(path):
        if cell.kind == "markdown":
            lines = cell.source.strip().splitlines()
            title = lines[0].strip() if lines else path.stem.replace("_", " ").title()
            start = 2 if len(lines) > 1 and set(lines[1].strip()) <= {"=", "-", "~"} else 1
            summary_lines: list[str] = []
            for line in lines[start:]:
                if not line.strip():
                    if summary_lines:
                        break
                    continue
                summary_lines.append(line.strip())
            summary = " ".join(summary_lines)
            return title.lstrip("# "), summary
    return path.stem.replace("_", " ").title(), ""


def markdown(text: str, source: Path) -> str:
    lines = text.strip().splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if index + 1 < len(lines) and re.fullmatch(r"[=\-~^]{3,}", lines[index + 1].strip()):
            level = {"=": "#", "-": "##", "~": "###", "^": "####"}[lines[index + 1].strip()[0]]
            output.append(f"{level} {line.strip()}")
            index += 2
            continue
        if line.lstrip().startswith(".. literalinclude::"):
            include = line.split("::", 1)[1].strip()
            options: dict[str, str] = {}
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith(":"):
                key, _, value = lines[index].strip().lstrip(":").partition(":")
                options[key] = value.strip()
                index += 1
            output.append(_literalinclude(source, include, options))
            continue
        line = RST_LINK.sub(lambda match: f"[{match.group(1)}]({match.group(2)})", line)
        output.append(ROLE.sub(lambda match: f"`{match.group(1)}`", line))
        index += 1
    return "\n".join(output).strip()


def _narrative(source: str) -> str | None:
    stripped = source.strip()
    try:
        module = ast.parse(stripped)
    except SyntaxError:
        module = None
    if module and len(module.body) == 1 and isinstance(module.body[0], ast.Expr):
        value = module.body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    lines = stripped.splitlines()
    meaningful = [line for line in lines if line.strip()]
    if meaningful and all(line.lstrip().startswith("#") for line in meaningful):
        visible = []
        in_metadata = False
        for line in lines:
            content = line.lstrip()[1:]
            content = content[1:] if content.startswith(" ") else content
            if content.strip() == "/// script":
                in_metadata = True
            elif content.strip() == "///" and in_metadata:
                in_metadata = False
            elif not in_metadata:
                visible.append(content)
        rendered = "\n".join(visible).strip()
        return rendered or None
    return None


def _is_license_preamble(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return (
        bool(lines)
        and all(line.lstrip().startswith("#") for line in lines)
        and any("SPDX-License" in line for line in lines)
    )


def _literalinclude(source: Path, include: str, options: dict[str, str]) -> str:
    target = (source.parent / include).resolve()
    if not target.exists():
        return f"> Source include unavailable: `{include}`"
    content = target.read_text(encoding="utf-8").splitlines()
    start_marker = options.get("start-after")
    end_marker = options.get("end-before")
    if start_marker:
        content = content[
            next((i + 1 for i, line in enumerate(content) if start_marker in line), 0) :
        ]
    if end_marker:
        content = content[
            : next((i for i, line in enumerate(content) if end_marker in line), len(content))
        ]
    language = options.get("language", target.suffix.lstrip("."))
    return f"```{language}\n" + "\n".join(content).rstrip() + "\n```"
