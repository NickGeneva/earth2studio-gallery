from pathlib import Path

from earth2studio_gallery.parser import cells, example_metadata, markdown


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
    assert "`package.Thing`" in rendered


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
