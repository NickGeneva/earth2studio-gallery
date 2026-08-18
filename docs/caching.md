# Cached results and rendering

Earth2Studio Gallery separates expensive execution results from disposable documentation
output.

## Durable results

`.e2sgallery/` contains the successful execution manifests, environment snapshots, captured
images, cell output, and telemetry. This is the state that a GPU workflow should retain
between runs. A result's
fingerprint covers the example source, resolved runner configuration, and gallery runner
version. It is not based on the repository commit, so unrelated commits do not invalidate an
example. Project-mode fingerprints also ignore `uv.lock` changes by default. Set
`invalidate_on_lock_change = true` to opt into lockfile-based invalidation.

During execution, relative files are written beneath
`.e2sgallery/runs/<example>/outputs/`. By default this directory is transient: the gallery
copies supported images into the retained `artifacts/` directory, then removes every remaining
execution output, including datasets, checkpoints, and temporary files. Set
`cache_output_directory = true` to retain the complete directory. Loading an older cache with
the default setting also removes legacy `work/` and `outputs/` directories.

Each run directory contains an `environment.json` snapshot captured from inside the isolated
UV harness. It records the actual interpreter, UV environment identifier, sorted installed
package versions and direct-source commits, UV version and sanitized invocation, effective
PEP 723 metadata, repository commit and dirty state, and the repository `uv.lock` hash. The
snapshot explicitly notes that a PEP 723 script environment is resolved independently from
the repository lockfile. The same provenance is included in the run's `manifest.json` but is
not embedded in downloadable notebooks.

Environment variables are available to UV and the example process at runtime, including values
configured through `runner.env`, but they are deliberately excluded from retained provenance.
Neither their names nor their values are written to the environment snapshot, manifest, or
downloadable notebook metadata.

Use `build` to update all stale results or a selected subset:

```console
# Run only examples whose fingerprints are stale or missing
uv run e2s-gallery build

# Re-run one section regardless of its fingerprint
uv run e2s-gallery build 02_plotting --force

# Re-run one example regardless of its fingerprint
uv run e2s-gallery build 02_plotting/01_sine_wave.py --force
```

## Disposable render

`docs/gallery/` is a derived view of the retained results. It contains generated Markdown,
optimized web images, source and notebook downloads, CSS, and the combined gallery index. It
can be deleted and recreated in full without executing an example:

```console
uv run e2s-gallery render
```

The command always discovers the complete example tree. This is intentional: a selective GPU
run can update only its cache entries, while the fast documentation job still produces a
complete and internally consistent gallery.

## Status labels

- **Cached** means the successful retained fingerprint matches the current example.
- **Stale** means retained output is available for display, but its fingerprint no longer
  matches the current source or runner settings.
- **Missing** means no successful retained output exists. The source page is still rendered,
  but it has no captured output.

A typical deployment stores `.e2sgallery/` on a durable results branch or object store. The
regular CPU documentation workflow restores it, runs `e2s-gallery render`, builds MkDocs, and
deploys a complete GitHub Pages artifact.
