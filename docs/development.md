# Development

[`tests/conftest.py`](../tests/conftest.py) connects runez's `ClickRunner` to `main()`;
[`tests/test_cli.py`](../tests/test_cli.py) checks captured stdout, stderr, and exit status.
These are integration tests as well as local fixture tests: package resolution reaches a
registry, Git inspection fetches a repository, and project inspection installs build tools.
An offline run cannot validate the whole suite.

The archives in [`tests/sample-dist/`](../tests/sample-dist/) cover current wheel metadata
and older source layouts. Use those fixtures for deterministic extraction regressions;
avoid making an archive-only case depend on the latest registry contents. The Git and
project tests pass the invoking interpreter explicitly to keep temporary builds aligned
with the test environment.

Run the configured checks from the repository root:

```shell
tox
tox -e py315
tox -e style,typecheck
.venv/bin/pytest tests/test_cli.py::test_dist_info -xvs
```

[`tox.ini`](../tox.ini) owns the default local environments, coverage aggregation, lint,
and type checking. Coverage uses separate files per tox environment so the aggregation
environment can combine them; its reports live under `.tox/`.
Use the existing `.venv/bin/python` explicitly for ad-hoc Python commands.

[`tests.yml`](../.github/workflows/tests.yml) runs the full supported minor-version matrix
using `tox -e py` under each selected interpreter. Local tox defaults test the oldest and
newest supported versions; they do not expand the hosted matrix automatically. CI runs
style separately; coverage aggregation and type checking are local tox checks.

[`release.yml`](../.github/workflows/release.yml) tests and builds on a version-tag push,
then publishes through PyPI trusted publishing. [`pyproject.toml`](../pyproject.toml) derives
versions from Git tags with setuptools-scm, including a dirty-tree local suffix. Publishing
depends on the workflow's `release` environment and OIDC permission, not a stored PyPI token.
Leave tagging and publishing to the maintainer unless explicitly requested.
