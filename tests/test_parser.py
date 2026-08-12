from pathlib import Path

from earth2studio_gallery.parser import cells, example_metadata, explicit_references, markdown


def test_parses_jupytext_gallery_cells(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    source.write_text(
        '''# SPDX-License-Identifier: Apache-2.0
# %%
"""
Useful Example
==============

Short explanation.
"""
# %%
# Run it
# ------
# This uses :py:class:`package.Thing`.
# %%
print("hello")
''',
        encoding="utf-8",
    )
    parsed = cells(source)
    assert [cell.kind for cell in parsed] == ["markdown", "markdown", "code"]
    assert example_metadata(source) == ("Useful Example", "Short explanation.")
    rendered = markdown(parsed[1].source, source)
    assert "## Run it" in rendered
    assert "[`package.Thing`][package.Thing]" in rendered


def test_python_roles_become_api_cross_references(tmp_path: Path) -> None:
    rendered = markdown(
        " ".join(
            (
                ":py:class:`package.module.Thing`",
                ":func:`~package.module.create`",
                ":py:meth:`custom label <~package.module.Thing.run>`",
                ":exc:`package.errors.Failure`",
            )
        ),
        tmp_path / "example.py",
    )

    assert rendered == " ".join(
        (
            "[`package.module.Thing`][package.module.Thing]",
            "[`create`][package.module.create]",
            "[`custom label`][package.module.Thing.run]",
            "[`package.errors.Failure`][package.errors.Failure]",
        )
    )

    resolved = markdown(
        ":func:`~package.module.create` and [`Thing`][package.module.Thing]",
        tmp_path / "example.py",
        {
            "package.module.create": "../../api/#package.module.create",
            "package.module.Thing": "../../api/#package.module.Thing",
        },
    )
    assert resolved == (
        "[`create`](../../api/#package.module.create) and "
        "[`Thing`](../../api/#package.module.Thing)"
    )


def test_literalinclude_is_resolved_without_sphinx(tmp_path: Path) -> None:
    (tmp_path / "library.py").write_text(
        "ignore\n# begin\nanswer = 42\n# end\nignore\n", encoding="utf-8"
    )
    rendered = markdown(
        """.. literalinclude:: library.py
   :language: python
   :start-after: # begin
   :end-before: # end""",
        tmp_path / "example.py",
    )
    assert rendered == "```python\nanswer = 42\n```"


def test_metadata_uses_only_first_narrative_paragraph(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    source.write_text(
        '''# %%
"""
Checkpointing a Forecast
========================

Basic inference workflow checkpointing.

This longer explanation belongs on the example page, not its gallery card.
"""
''',
        encoding="utf-8",
    )

    assert example_metadata(source) == (
        "Checkpointing a Forecast",
        "Basic inference workflow checkpointing.",
    )


def test_rst_external_link_is_converted_without_sphinx(tmp_path: Path) -> None:
    rendered = markdown(
        "Open an `Earth2Studio issue <https://github.com/NVIDIA/earth2studio/issues>`_.",
        tmp_path / "example.py",
    )

    assert rendered == (
        "Open an [Earth2Studio issue](https://github.com/NVIDIA/earth2studio/issues)."
    )


def test_explicit_references_only_scan_narrative_cells(tmp_path: Path) -> None:
    source = tmp_path / "references.py"
    source.write_text(
        '''# %%
"""
Use [`Widget`][package.models.Widget], [package.models.Other][], and
:func:`~package.workflows.run`. A normal [website](https://example.com) is ignored.
"""
# %%
from package.models import Hidden

Hidden()
''',
        encoding="utf-8",
    )

    assert explicit_references(source) == {
        "package.models.Other",
        "package.models.Widget",
        "package.workflows.run",
    }
