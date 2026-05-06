# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-file CLI tool (`uv_metadata.py`) that inspects Python package metadata without installing.
Published on PyPI as `uv-metadata`, runnable via `uvx uv-metadata`. Requires `uv` on PATH.

## Commands

```shell
# Run all checks (tests on py310+py314, coverage, ruff, pyright)
tox

# Run tests only (single Python version)
tox -e py311

# Run a single test
.venv/bin/pytest tests/test_cli.py::test_package -xvs

# Lint and format check
tox -e style

# Auto-fix lint/format
tox -e reformat

# Type check
tox -e typecheck

# Run the tool locally
.venv/bin/uv-metadata requests
.venv/bin/uv-metadata .
```

## Architecture

All logic lives in `uv_metadata.py`. The flow is:

1. **`main()`** — CLI entry point (argparse), calls `get_metadata_from_pip_spec()`
2. **`get_metadata_from_pip_spec()`** — routes input to the right extraction strategy:
   - Local files (.whl/.zip/.tar.gz) → `extract_metadata_from_file()` → `ZipReader`/`TarReader`
   - Local dist-info/egg-info dir → `extract_metadata_from_dist_info()`
   - Local project folder → `extract_metadata_from_project_folder()` (PEP 517 build)
   - Git/URL refs → `extract_metadata_from_uv_install()` (temp install via uv)
   - Plain package names → `extract_metadata_from_uv_resolve()` (fast: resolve + stream wheel metadata via HTTP range requests, fallback: download sdist)
3. **All paths converge** on `extract_metadata_from_dist_info()` which uses `importlib.metadata.PathDistribution`

Key design details:
- Archive extraction uses a `MetadataReader` ABC with `ZipReader` and `TarReader` subclasses (context managers)
- Two compiled regexes (`_INFO_DIR_RX`, `_ROOT_PKG_INFO_RX`) drive metadata file discovery, built from the `METADATA_FILES` tuple
- `PKG-INFO` files are renamed to `METADATA` before reading so `PathDistribution` handles both formats
- `UNKNOWN` sentinel values from old metadata are filtered out
- `description` (long description) is stripped by default; `--full` flag preserves it
- `dynamic` is stripped by default; `--full` flag preserves it
- `canonical_git_url()` accepts plain GitHub HTTPS URLs and `git@` SSH shorthand

## Testing

Tests use the `runez` library's `ClickRunner` fixture (`cli`). The pattern is:
```python
def test_example(cli):
    cli.run("requests", "-kversion")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
```

Test fixtures in `tests/sample-dist/` include real archived packages (colorama, mock, uv-metadata itself).

## Versioning

Uses `setuptools-scm` with `local_scheme = "dirty-tag"`. Version is derived from git tags (`v*`).
Release workflow triggers on tag push, publishes to PyPI via trusted publishing.
