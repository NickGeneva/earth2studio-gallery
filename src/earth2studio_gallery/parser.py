from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

CELL = re.compile(r"^#\s*%%.*$", re.MULTILINE)
PYTHON_ROLE = re.compile(
    r":(?:py:)?(?:attr|class|const|data|exc|func|meth|mod|obj):`(?P<short>~)?(?P<body>[^`]+)`"
)
RST_LINK = re.compile(r"`([^`<>]+?)\s*<([^<>]+)>`_")
PYTHON_TARGET = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+"
MARKDOWN_REFERENCE = re.compile(
    rf"\[(?P<label>[^\]\n]+)\]\[(?P<target>{PYTHON_TARGET})\]|"
    rf"\[(?P<collapsed>{PYTHON_TARGET})\]\[\]"
)


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


def markdown(text: str, source: Path, reference_links: dict[str, str] | None = None) -> str:
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
        output.append(PYTHON_ROLE.sub(_python_reference, line))
        index += 1
    rendered = "\n".join(output).strip()
    if not reference_links:
        return rendered

    def resolve(match: re.Match[str]) -> str:
        target = match.group("target") or match.group("collapsed")
        url = reference_links.get(target)
        if not url:
            return match.group(0)
        return f"[{match.group('label') or target}]({url})"

    return MARKDOWN_REFERENCE.sub(resolve, rendered)


def explicit_references(path: Path) -> set[str]:
    """Return explicitly linked Python objects from narrative cells only."""
    found: set[str] = set()
    for cell in cells(path):
        if cell.kind != "markdown":
            continue
        for match in PYTHON_ROLE.finditer(cell.source):
            body = match.group("body").strip()
            explicit = re.fullmatch(r".+?\s*<\s*([^<>]+?)\s*>", body)
            target = explicit.group(1) if explicit else body
            target = target.removeprefix("~").strip()
            if re.fullmatch(PYTHON_TARGET, target):
                found.add(target)
        for match in MARKDOWN_REFERENCE.finditer(cell.source):
            found.add(match.group("target") or match.group("collapsed"))
    return found


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


def _python_reference(match: re.Match[str]) -> str:
    """Convert a Sphinx Python role to an mkdocstrings/autorefs link."""
    body = match.group("body").strip()
    explicit = re.fullmatch(r"(.+?)\s*<\s*([^<>]+?)\s*>", body)
    if explicit:
        label, target = explicit.groups()
    else:
        target = body
        label = target.rsplit(".", 1)[-1] if match.group("short") else target
    return f"[`{label.strip()}`][{target.strip()}]"


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
