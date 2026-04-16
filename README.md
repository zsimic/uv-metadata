# uv-metadata

Extract Python package metadata from any source without installing.

```shell
$ uvx uv-metadata requests -kversion
2.32.4

$ uvx uv-metadata requests -krequires_python
>=3.10

$ uvx uv-metadata 'pip<23' -kversion
22.3.1
```

Works with published packages, local wheels/sdists, project folders, and git repos.
For published packages, metadata is streamed directly from the remote wheel via HTTP range
requests — typically a few KB, no full download needed.

This project also serves as a reference implementation for a proposed native
[`uv metadata`](uv-metadata-spec.md) subcommand
(see [astral-sh/uv#6037](https://github.com/astral-sh/uv/issues/6037) and the [spec](uv-metadata-spec.md)).

Requires `uv` on `PATH`.


## Installation

```shell
# Run directly (no install needed)
uvx uv-metadata requests

# Or install permanently
uv tool install uv-metadata
```


## Quick examples

```shell
# Full metadata as JSON
uvx uv-metadata flask

# Single key
uvx uv-metadata flask -kversion

# Version constraint
uvx uv-metadata 'flask<3' -kversion

# Local project
uvx uv-metadata .

# Local wheel or sdist
uvx uv-metadata ./dist/mypackage-1.0.0-py3-none-any.whl

# Git repo
uvx uv-metadata git+https://github.com/psf/requests@main

# Target a specific Python version
uvx uv-metadata numpy -p3.9 -kversion
```


## Input routing

| Input | Strategy |
|---|---|
| `.`, `./path`, `/abs/path`, or any existing filesystem path | |
| &emsp;directory with `pyproject.toml` or `setup.py` | Build metadata via PEP 517 |
| &emsp;`*.dist-info` or `*.egg-info` directory | Read directly |
| &emsp;`*.whl` or `*.zip` file | Extract from zip archive |
| &emsp;`*.tar.gz` file | Extract from tarball |
| `git+https://...`, `git@...`, or `pkg @ url` | Install to temp dir, read dist-info |
| plain name or version constraint (`name`, `name>=x`, etc.) | Resolve via uv, stream dist-info from remote wheel; fall back to downloading sdist |


## Output format

JSON with sorted keys. The `description` (long description) field is omitted by default
as it is typically very large; use `--full` to include it.

```shell
$ uvx uv-metadata pip
{
    "author_email": "The pip developers <distutils-sig@python.org>",
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        ...
    ],
    "description_content_type": "text/x-rst",
    "entry_points": {
        "console_scripts": {
            "pip": "pip._internal.cli.main:main",
            "pip3": "pip._internal.cli.main:main"
        }
    },
    "license_expression": "MIT",
    "metadata_version": "2.4",
    "name": "pip",
    "project_url": [
        "Documentation, https://pip.pypa.io",
        "Source, https://github.com/pypa/pip"
    ],
    "requires_python": ">=3.9",
    "summary": "The PyPA recommended tool for installing Python packages.",
    "version": "26.0.1"
}
```

Structural rules:
- Keys are `lower_snake_case`
- Single-occurrence fields: plain string
- Multi-occurrence fields: list of strings
- `entry_points`: `{"group": {"name": "module:attr"}}`
- `top_level`: list of top-level importable names
- `UNKNOWN` values are omitted


## CLI reference

```
usage: uv-metadata [-h] [-p PYTHON] [-k KEY] [--full] [package]

Output the metadata of a package, in machine-readable format

positional arguments:
  package              Package to inspect (default: current folder)

options:
  -h, --help           show this help message and exit
  -p, --python PYTHON  Python version to target (e.g. 3.11)
  -k, --key KEY        Show only this key from the metadata
  --full               Include full description in output
```


## How it works

### Fast path for published packages

1. `uv pip compile --format pylock.toml` resolves to a concrete wheel URL without downloading
2. `SeekableHttpFile` + `ZipFile` streams only the dist-info files via HTTP range requests
3. Falls back to downloading the sdist when no wheel is available

### Unified metadata reading

All extraction strategies produce a dist-info folder which is read by
`importlib.metadata.PathDistribution`. Both `METADATA` (wheels) and `PKG-INFO` (sdists)
are handled transparently.

### Archive extraction

A `MetadataReader` base class with `ZipReader` and `TarReader` implementations provides
uniform member discovery and extraction across archive formats.


## Dependencies

| Package | Purpose |
|---|---|
| [`build`](https://pypi.org/project/build/) | PEP 517 metadata building for local project folders |
| [`pyproject-hooks`](https://pypi.org/project/pyproject-hooks/) | Quiet subprocess runner used by `build` |
| [`seekablehttpfile`](https://pypi.org/project/seekablehttpfile/) | HTTP range requests for streaming dist-info from remote wheels |


## Relevant PEPs

- [PEP 241](https://peps.python.org/pep-0241/) – Metadata for Python Software Packages 1.0
- [PEP 314](https://peps.python.org/pep-0314/) – Metadata for Python Software Packages 1.1
- [PEP 345](https://peps.python.org/pep-0345/) – Metadata for Python Software Packages 1.2
- [PEP 566](https://peps.python.org/pep-0566/) – Metadata for Python Software Packages 2.1
- [PEP 508](https://peps.python.org/pep-0508/) – Dependency specification for Python Software Packages
- [PEP 517](https://peps.python.org/pep-0517/) – A build-system independent format for source trees
- [PEP 643](https://peps.python.org/pep-0643/) – Metadata for Package Source Distributions
- [PEP 658](https://peps.python.org/pep-0658/) – Serve Distribution Metadata in the Simple Repository API
- [PEP 639](https://peps.python.org/pep-0639/) – Improving License Clarity with Better Package Metadata
