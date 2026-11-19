# Architecture

Start in [`uv_metadata.py`](../uv_metadata.py) at `get_metadata_from_pip_spec()` when changing
source handling. Existing paths win over package specifications; wheel URLs are recognized
before the generic URL/Git branch. Preserve that order so direct wheel references keep
their streaming path. `canonical_git_url()` also accepts copied GitHub HTTPS URLs and
SSH shorthand; it uses URL heuristics rather than probing the remote.

Published-name resolution and source-tree inspection have different costs:

- `extract_metadata_from_uv_resolve()` asks uv for a universal pylock, then streams a wheel
  or downloads a source archive. Its default Python target is deliberately `99` so the
  interpreter running the CLI does not limit the latest package version. An explicit
  Python target overrides that choice. The pylock is searched with regular expressions;
  changes to uv's output shape need an integration check.
- `extract_metadata_from_project_folder()` creates a temporary uv environment and installs
  build requirements through `_UvIsolatedEnv`. `ProjectBuilder.metadata_path()` can fall
  back to building a wheel when the backend lacks a metadata hook. It executes backend code.
- `extract_metadata_from_uv_install()` handles Git and other URL references with a temporary
  install. It disables runtime dependency installation and expects exactly one dist-info folder.

All paths converge on `extract_metadata_from_dist_info()` and `PathDistribution`.
Archive readers copy selected metadata members into a synthetic dist-info directory and
rename `PKG-INFO` to `METADATA`. Directory metadata takes precedence over the archive's
root package `PKG-INFO`; old source archives depend on that fallback. Streaming reads the
ZIP directory as well as metadata members, so it is not a PEP 658 sidecar-metadata request.

Normalization belongs to the shared reader: legacy `UNKNOWN` and empty values disappear,
and entry points and top-level imports come from their companion files. Keep CLI-only
filtering in `main()`: library callers receive `description` and `dynamic`, while the CLI
removes them before key selection unless `--full` is set.

For build failures, `_build_backend_problem()` chooses the last recognized error line.
The quiet backend runner preserves captured output for `-v`; printing it unconditionally
would break the concise stderr behavior covered by the tests.

`UV_PATH` is captured at import time from `$UV` or `PATH`. Tests that replace it or change
logging must account for module state, since the CLI harness calls `main()` in-process.
