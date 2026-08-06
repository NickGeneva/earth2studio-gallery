# Cached results and rendering

Earth2Studio Gallery separates expensive execution results from disposable documentation
output.

## Durable results

`.e2sgallery/` contains the successful execution manifests, captured images, cell output, and
telemetry. This is the state that a GPU workflow should retain between runs. A result's
fingerprint covers the example source, resolved runner configuration, and gallery runner
version. It is not based on the repository commit, so unrelated commits do not invalidate an
example.

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
