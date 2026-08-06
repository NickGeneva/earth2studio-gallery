from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .config import GalleryConfig
from .discovery import Example, discover
from .progress import ProgressCallback, report
from .render import render_example, render_indexes, write_css
from .runner import RunResult, cached_result, run_example


@dataclass(slots=True)
class BuildReport:
    examples: list[Example]
    results: dict[str, RunResult | None]

    @property
    def failures(self) -> list[tuple[Example, RunResult]]:
        return [
            (example, result)
            for example in self.examples
            if (result := self.results.get(example.slug)) is not None and result.returncode != 0
        ]


class GalleryBuilder:
    def __init__(self, config: GalleryConfig, progress: ProgressCallback | None = None):
        self.config = config
        self.progress = progress

    def build(
        self,
        selectors: list[str] | None = None,
        *,
        execute: str | None = None,
        force: bool = False,
    ) -> BuildReport:
        examples = discover(self.config, selectors)
        report(self.progress, "discover", f"selected {len(examples)} example(s)")
        mode = execute or self.config.execute
        results: dict[str, RunResult | None] = {example.slug: None for example in examples}
        runnable = [
            example for example in examples if self.config.example_config(example.source).execute
        ]
        if mode == "never":
            for example in examples:
                results[example.slug] = cached_result(example, self.config)
                result = results[example.slug]
                if result is None:
                    status = "missing retained run"
                elif result.stale:
                    status = "loaded stale retained artifacts"
                else:
                    status = "loaded cached artifacts"
                report(self.progress, "cache", status, example.relative.as_posix())
        else:
            if self.config.jobs == 1:
                for position, example in enumerate(runnable, 1):
                    name = example.relative.as_posix()
                    report(
                        self.progress,
                        "example",
                        f"starting {position}/{len(runnable)}",
                        name,
                    )
                    result = run_example(
                        example,
                        self.config,
                        force=force or mode == "always",
                        progress=self.progress,
                    )
                    results[example.slug] = result
                    if result.returncode and self.config.fail_fast:
                        break
            else:
                with ThreadPoolExecutor(max_workers=self.config.jobs) as pool:
                    futures = {
                        pool.submit(
                            run_example,
                            example,
                            self.config,
                            force=force or mode == "always",
                            progress=self.progress,
                        ): example
                        for example in runnable
                    }
                    for future in as_completed(futures):
                        example = futures[future]
                        results[example.slug] = future.result()
        for example in examples:
            render_example(
                example,
                results[example.slug],
                self.config,
                progress=self.progress,
            )
        report(self.progress, "index", "rendering combined gallery index")
        render_indexes(examples, results, self.config)
        write_css(self.config)
        failures = sum(1 for result in results.values() if result and result.returncode)
        report(
            self.progress,
            "complete",
            f"finished {len(examples)} example(s), {failures} failure(s)",
        )
        return BuildReport(examples, results)

    def render(self) -> BuildReport:
        """Recreate the complete gallery from retained execution results."""
        return self.build(execute="never")
