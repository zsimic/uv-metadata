# Native uv proposal

This repository provides a Python reference implementation for the native `uv metadata`
command proposed in [astral-sh/uv#6037](https://github.com/astral-sh/uv/issues/6037).
The motivation is a single metadata-inspection command for automation: existing approaches
often assume an installed distribution or require callers to unpack archives themselves.

The implemented input and output contract lives in the [README](../README.md).
Use [`uv_metadata.py`](../uv_metadata.py) and its [tests](../tests/test_cli.py) as the
behavioral reference; the native command is a proposal, not a command shipped by this repo.

The useful properties to carry into a native implementation are consistent metadata across
source types, small wheel-metadata transfers, explicit Python targeting, and output that
shell scripts can consume either as JSON or a selected value. The [architecture notes](architecture.md)
explain where the Python implementation uses a build or temporary install to achieve this.

A native implementation could improve on the current approach by:

- Calling uv's resolver directly instead of shelling out and searching pylock text.
- Reusing uv's cache for metadata retrieval rather than making independent HTTP requests.
- Using [PEP 658](https://peps.python.org/pep-0658/) index metadata to avoid reading a wheel.

Those are design opportunities, not behavior promised by this implementation. In particular,
the current remote-wheel reader uses HTTP ranges through `SeekableHttpFile`, and local
project inspection still runs the project's PEP 517 backend.
