# Proposed `uv metadata` subcommand

This document describes the behavior of a proposed `uv metadata` subcommand
(see [astral-sh/uv#6037](https://github.com/astral-sh/uv/issues/6037)). The Python
proof-of-concept in this repo ([`uv_metadata.py`](uv_metadata.py)) implements this spec and
can serve as a reference for a native Rust implementation in uv.


## Motivation

There is currently no simple way to inspect a Python package's metadata without installing it.
Common workarounds (`pip show`, `importlib.metadata`, `pkginfo`) all require the package to be
installed, or involve manual archive extraction. A dedicated `uv metadata` subcommand would make
this a first-class operation — useful for CI pipelines, dependency auditing, tooling integration,
and general inspection.


## Design principles

- **No install required** for published packages — resolve and stream metadata only
- **Uniform JSON output** regardless of source (PyPI, local wheel, sdist, git repo, project folder)
- **Minimal by default** — omit the (often large) `description` field unless `--full` is given
- **Single package at a time** — fits naturally into shell pipelines and scripting


## Synopsis

```
uv metadata [OPTIONS] [PACKAGE]
```

Output metadata for the specified package in machine-readable JSON format.

### Arguments

- `[PACKAGE]` — Package to inspect. Accepts any of:
  - Plain name or version constraint: `requests`, `requests>=2.28`
  - Local path: `.`, `./dist/foo-1.0.whl`, `./dist/foo-1.0.tar.gz`, `./dist/foo-1.0.zip`
  - Dist-info / egg-info directory: `./foo-1.0.dist-info`
  - Git URL: `git+https://github.com/user/repo@ref`
  - Direct reference: `foo @ https://example.com/foo-1.0.whl`
  - Default: current directory (equivalent to `.`)

### Options

- `-k, --key <KEY>` — Show only the value of the specified metadata key (raw string or JSON)
- `-p, --python <VERSION>` — Target Python version for resolution (e.g. `3.11`)
- `--full` — Include the `description` (long description) field in output


## Resolution strategy

For published packages, the command should:

1. Resolve to a concrete version using uv's existing resolver
2. Prefer streaming metadata from the wheel's dist-info via HTTP range requests (a few KB)
3. Fall back to downloading the sdist if no wheel is available

A native Rust implementation could go further:
- Use uv's cache to avoid network requests for already-resolved packages
- Leverage PEP 658 metadata (if the index supports it) to skip the wheel entirely
- Access the package index directly without shelling out to `uv pip compile`


## Output format

Default output is JSON with sorted keys:

```json
{
    "entry_points": {
        "console_scripts": {
            "uv-metadata": "uv_metadata:main"
        }
    },
    "metadata_version": "2.4",
    "name": "uv-metadata",
    "requires_dist": [
        "build",
        "pyproject-hooks",
        "seekablehttpfile"
    ],
    "requires_python": ">=3.11",
    "version": "1.0.0"
}
```

### Structural rules

- Keys are `lower_snake_case` (normalized per PEP 566: `re.sub(r"\W", "_", key).lower()`)
- Single-occurrence fields: plain string value
- Multi-occurrence fields (`classifiers`, `requires_dist`, `project_url`, ...): list of strings
- `entry_points`: nested object `{"group": {"name": "module:attr"}}`
- `top_level`: list of top-level importable package names (from `top_level.txt`)
- `UNKNOWN` values: omitted entirely
- `description`: omitted by default (use `--full` to include)

With `-k <KEY>`: prints the raw string value for single-value keys, or JSON for structured/list values.


## Exit codes

- `0` — success
- `1` — error (package not found, resolution failure, missing key, etc.) with message on stderr
