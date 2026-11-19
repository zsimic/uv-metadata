# Maintainer map

`uv-metadata` turns several kinds of Python package sources into the same metadata dictionary.
The CLI, routing, extraction, and subprocess integration all live in
[`uv_metadata.py`](../uv_metadata.py); the [README](../README.md) owns user-facing usage.

Start with the question your change needs to answer:

- [Architecture](architecture.md): where inputs converge, how resolution differs from
  building, and which compatibility details extraction must preserve.
- [Development](development.md): how the test harness reaches the CLI, which checks differ
  between local tox and CI, and how releases get their version and publish credentials.
- [Native uv proposal](uv-metadata-proposal.md): the motivation for a native command and
  the boundary between this implementation and ideas for uv itself.

Dependency declarations and the supported runtime floor live in
[`pyproject.toml`](../pyproject.toml). Test environments and tool configuration live in
[`tox.ini`](../tox.ini); the exact hosted matrix lives in
[`tests.yml`](../.github/workflows/tests.yml).
