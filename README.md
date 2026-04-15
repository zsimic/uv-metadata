# uv-metadata

Python proof-of-concept implementation of a proposed `uv metadata` subcommand.

This repo serves as a reference spec for a future Rust implementation in uv. It demonstrates
how to fetch Python package metadata from any source — published packages, local files, remote
wheels, git repos — without performing a full package install where avoidable.

`uv` must be available on `PATH`.


## Input routing

The command accepts a single package specification and routes to the appropriate extraction strategy:

| Input | Strategy |
|---|---|
| `.`, `./path`, `/abs/path`, or any existing filesystem path | |
| &emsp;directory with `pyproject.toml` or `setup.py` | Build metadata via PEP 517 (using the `build` library) |
| &emsp;`*.dist-info` or `*.egg-info` directory | Read directly via `importlib.metadata.PathDistribution` |
| &emsp;`*.whl` file | Extract dist-info files from the zip archive |
| &emsp;`*.tar.gz` file | Extract dist-info / egg-info files from the tarball |
| `git+https://...`, `git@...`, or `pkg @ url` | Install to temp dir via `uv pip install --no-deps --target`, read dist-info |
| plain name or version constraint (`name`, `name>=x`, etc.) | Resolve wheel URL via `uv pip compile`, stream dist-info via HTTP range requests |


## Key implementation choices

### Fast path for plain package names

For plain package names (`requests`, `requests>=2.28`, ...) a full install is avoided:

1. `uv pip compile --format pylock.toml --no-deps` resolves the package to a concrete wheel URL
   without downloading anything
2. The wheel URL is extracted from the TOML output via a simple regex
3. `SeekableHttpFile` + `ZipFile` issues HTTP range requests to fetch only the dist-info files
   from the remote wheel — typically a few KB instead of downloading the full wheel

### Unified metadata reading

All strategies funnel into one function:

```python
extract_metadata_from_dist_info(folder: Path) -> dict
```

It uses `importlib.metadata.PathDistribution` to parse the metadata files. This handles both
`METADATA` (wheels / dist-info) and `PKG-INFO` (sdists / egg-info) transparently; `PKG-INFO`
is renamed to `METADATA` before reading so `PathDistribution` can find it in either case.

### Archive extraction

Both zip files (wheels) and tarballs (sdists) use the same helper:

```python
_extract_dist_info_files(info_dir, prefix, names, read_fn)
```

It iterates over `METADATA_FILES = ("METADATA", "PKG-INFO", "entry_points.txt", "top_level.txt")`,
copies each that exists under `prefix` into `info_dir` (renaming `PKG-INFO` → `METADATA`), then
`extract_metadata_from_dist_info` reads the result. This means the local-wheel path and the
streamed-remote-wheel path share exactly the same extraction code (`_extract_from_zipfile`).

For tarballs, the first match of `*.dist-info/` or `*.egg-info/` containing `METADATA` or
`PKG-INFO` wins. A fallback handles older sdists that have only a root-level `PKG-INFO`.

### Metadata key normalization

Keys are normalized identically to how [pkginfo](https://github.com/jwilk-mirrors/python-pkginfo/blob/master/pkginfo/distribution.py#L34) does it:

```python
re.sub(r"\W", "_", key).lower()
```

One alias is applied: `classifier` → `classifiers` (PEP 301 pluralized the field name).

Multi-value fields (e.g. `classifiers`, `requires_dist`, `project_url`) are accumulated as lists.
`UNKNOWN` values are dropped.

`entry_points` is structured as `{group: {name: value}}`. `top_level` is a list of top-level
import names read from `top_level.txt`.


## Output format

JSON output with these structural rules:
- Keys are `lower_snake_case`
- Single-occurrence fields: plain string
- Multi-occurrence fields: list of strings
- `entry_points`: `{"group": {"name": "module:attr"}}`
- `top_level`: list of top-level importable names
- `UNKNOWN` values are omitted entirely


## Examples

### Published package (fast path — no install)

```shell
$ uv-metadata pip
{
    "author_email": "The pip developers <distutils-sig@python.org>",
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        ...
        "Programming Language :: Python :: Implementation :: PyPy"
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

### Version constraint

```shell
$ uv-metadata 'pip<23' -kversion
22.3.1
```

### Single metadata key

```shell
$ uv-metadata requests -krequires_python
>=3.10

$ uv-metadata requests -kproject_url
[
    "Documentation, https://requests.readthedocs.io",
    "Source, https://github.com/psf/requests"
]
```

### Local project folder (PEP 517 build)

```shell
$ uv-metadata .
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
    "top_level": [
        "uv_metadata"
    ],
    "version": "1.0.0"
}
```

### Local wheel or sdist

```shell
$ uv-metadata ./dist/mypackage-1.0.0-py3-none-any.whl -kname
mypackage

$ uv-metadata ./dist/mypackage-1.0.0.tar.gz -kversion
1.0.0
```

### Git URL (installs to temp dir, reads dist-info)

```shell
$ uv-metadata git+https://github.com/zsimic/uv-metadata@main
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
    "top_level": [
        "uv_metadata"
    ],
    "version": "1.0.0"
}
```

### Target a specific Python version

```shell
$ uv-metadata 'numpy' -p3.9 -kversion
2.2.5
```


## CLI synopsis

```
usage: uv-metadata [-h] [-p PYTHON] [-k KEY] [package]

Output the metadata of a package, in machine-readable format

positional arguments:
  package     Package to inspect (default: current folder)

options:
  -h, --help           show this help message and exit
  -p, --python PYTHON  Python version to target (e.g. 3.11)
  -k, --key KEY        Show only this key from the metadata
```


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
- [PEP 426](https://peps.python.org/pep-0426/) – Metadata for Python Software Packages 2.0
- [PEP 566](https://peps.python.org/pep-0566/) – Metadata for Python Software Packages 2.1
- [PEP 508](https://peps.python.org/pep-0508/) – Dependency specification for Python Software Packages
- [PEP 517](https://peps.python.org/pep-0517/) – A build-system independent format for source trees
- [PEP 643](https://peps.python.org/pep-0643/) – Metadata for Package Source Distributions
- [PEP 658](https://peps.python.org/pep-0658/) – Serve Distribution Metadata in the Simple Repository API
- [PEP 685](https://peps.python.org/pep-0685/) – Comparison of extra names for optional distribution dependencies
- [PEP 639](https://peps.python.org/pep-0639/) – Improving License Clarity with Better Package Metadata

`pkginfo` has a useful
[overview](https://github.com/jwilk-mirrors/python-pkginfo/blob/master/pkginfo/distribution.py#L34)
of which fields were introduced in each metadata version.
