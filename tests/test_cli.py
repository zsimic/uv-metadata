import json

import runez


def test_bogus(cli):
    cli.run("a--bogus-package-that-does-not-exist--z")
    assert cli.failed
    assert cli.logged.stderr.contents().strip() == "Package 'a--bogus-package-that-does-not-exist--z' does not exist"


def test_dist_info(cli):
    # Verify that getting metadata on non-existing file fails properly
    cli.run("./sample-1.0-py3-none-any.whl")
    assert cli.failed
    assert "does not exist" in cli.logged

    runez.ensure_folder("sample/sample-1.0.dist-info", logger=None)
    cli.run("sample/sample-1.0.dist-info")
    assert cli.failed
    assert "No metadata files in sample-1.0.dist-info"

    # Build a minimal .whl and then run against the extracted dist-info
    meta = "Metadata-Version: 2.1\nName: sample\nVersion: 1.0\nSummary: A test package\n"
    runez.write("sample/sample-1.0.dist-info/METADATA", meta, logger=None)
    runez.compress("sample/sample-1.0.dist-info", "sample-1.0-py3-none-any.whl", ext="zip", logger=None)

    # Test against an extracted .dist-info folder
    cli.run("sample/sample-1.0.dist-info")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "sample"
    assert payload["version"] == "1.0"
    assert payload["summary"] == "A test package"

    # Test against the .whl file
    cli.run("sample-1.0-py3-none-any.whl")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "sample"
    assert payload["version"] == "1.0"
    assert payload["summary"] == "A test package"


def test_git_url(cli):
    cli.run(f"-p{runez.SYS_INFO.invoker_python}", "git@github.com:zsimic/uv-metadata.git")
    assert cli.succeeded
    assert '"name": "uv-metadata"' in cli.logged.stdout


def test_missing_wheel(cli):
    cli.run("pycparser<2.15")
    assert cli.failed
    assert "No wheel available for pycparser<2.15" in cli.logged


def test_package(cli):
    cli.run("pip")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert "pip" in payload["entry_points"]["console_scripts"]
    assert payload["name"] == "pip"
    assert payload["version"]

    cli.run("coverage", "-khome_page")
    assert cli.succeeded
    assert "http" in cli.logged.stdout


def test_project_dist(cli):
    tests_folder = runez.to_path(cli.tests_folder) / "sample-dist"
    cli.run(tests_folder / "uv_metadata-1.0.0.tar.gz")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["entry_points"]["console_scripts"]["uv-metadata"] == "uv_metadata:main"
    assert payload["name"] == "uv-metadata"
    assert payload["top_level"] == ["uv_metadata"]

    cli.run(tests_folder / "uv_metadata-1.0.0-py3-none-any.whl")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["entry_points"]["console_scripts"]["uv-metadata"] == "uv_metadata:main"
    assert payload["name"] == "uv-metadata"
    assert payload["top_level"] == ["uv_metadata"]

    cli.run(tests_folder / "mock-0.6.0.tar.gz")
    assert cli.succeeded
    assert '"name": "mock",' in cli.logged.stdout


def test_project_folder(cli):
    with runez.CurrentFolder(cli.project_folder):
        cli.run(f"-p{runez.SYS_INFO.invoker_python}")
        assert cli.succeeded
        payload = json.loads(cli.logged.stdout.contents())
        assert payload["entry_points"]["console_scripts"]["uv-metadata"] == "uv_metadata:main"
        assert payload["name"] == "uv-metadata"
        assert payload["top_level"] == ["uv_metadata"]

    cli.run(cli.tests_folder)
    assert cli.failed
    assert "no pyproject.toml or setup.py" in cli.logged


def test_single_key(cli):
    cli.run(cli.project_folder, "-kname")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "uv-metadata"

    cli.run(cli.project_folder, "-kname2")
    assert cli.failed
    assert "no key 'name2' in metadata" in cli.logged
