# uv-metadata

Inspect Python package metadata as JSON from published packages, local wheels and sdists,
project folders, and Git repositories.

```shell
# Inspect a published package
uvx uv-metadata requests

# Print a single value, suitable for scripts
uvx uv-metadata requests -kversion

# Combine a version constraint with a target Python version
uvx uv-metadata 'setuptools<70' -p3.7 -kversion
```

Published wheel metadata is streamed via HTTP range requests, usually fetching only a few KB.
Local archives and metadata directories are read directly. Project folders run their build
backend in a temporary environment; Git and other non-wheel URL references use a temporary
package install without runtime dependencies. Your environment is not the install target.

Requires Python 3.10 or newer and `uv`. When launched with `uvx` or `uv run`, the tool uses
the executable identified by `$UV`; otherwise it looks for `uv` on `PATH`.

## Installation

Run directly with `uvx`, as above, or install a persistent command:

```shell
uv tool install uv-metadata
uv-metadata requests
```

## Inputs

Omitting the package inspects the current project folder.

```shell
# Local project: prepare metadata through its PEP 517 build backend
uvx uv-metadata .

# Local wheel, sdist (.tar.gz or .zip), or extracted metadata directory
uvx uv-metadata ./dist/mypackage-1.0.0-py3-none-any.whl
uvx uv-metadata ./dist/mypackage-1.0.0.tar.gz
uvx uv-metadata ./mypackage-1.0.0.dist-info

# Remote wheel: stream its metadata
uvx uv-metadata https://example.com/mypackage-1.0.0-py3-none-any.whl
uvx uv-metadata 'mypackage @ https://example.com/mypackage-1.0.0-py3-none-any.whl'

# Git repository, optionally at a revision
uvx uv-metadata git+https://github.com/psf/requests@main
```

Existing filesystem paths take precedence over package names. Use a path prefix such as `./`
when referring to a local file that may be missing, so it is treated as a path.
Both `.dist-info` and `.egg-info` directories are accepted. Published packages without a
wheel fall back to downloading and reading a source archive.

## Output and options

The default output is an indented JSON object with sorted keys:

- Metadata keys use `lower_snake_case`.
- Single-value fields are strings; repeatable fields such as `requires_dist` are lists.
- `entry_points` groups entries as `{"group": {"name": "module:attr"}}`.
- `top_level`, when supplied by the package, lists top-level import names.
- Empty fields and legacy `UNKNOWN` values are omitted.
- `description` and `dynamic` are omitted unless `--full` is given.

```shell
# Raw string for a single-value key; JSON for a list or object
uvx uv-metadata flask -kversion
uvx uv-metadata flask -krequires_dist

# Include the long description and dynamic metadata declarations
uvx uv-metadata flask --full

# Print just the long description
uvx uv-metadata flask --full -kdescription

# Show full build-backend output when inspecting a project fails
uvx uv-metadata . -v

# Current option reference
uvx uv-metadata --help
```

`-p` / `--python` selects the Python target for package resolution, project metadata builds,
and temporary installs. Reading an existing archive or metadata directory does not resolve
it for another Python version. Without `-p`, published-package resolution seeks the latest
release independently of the Python running this command.

A missing key or extraction failure exits with an error message on stderr and a nonzero status.
`--full` is needed when selecting an otherwise omitted key, such as `-kdescription`.

## Native uv proposal

This project is a Python reference implementation for the proposed native `uv metadata`
subcommand discussed in [astral-sh/uv#6037](https://github.com/astral-sh/uv/issues/6037).
