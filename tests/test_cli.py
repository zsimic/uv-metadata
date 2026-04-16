import json

import runez

from uv_metadata import canonical_git_url


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
    # 'git@' urls are not always usable from CI, like GH actions
    assert canonical_git_url("git@github.com:zsimic/uv-metadata.git") == "git+ssh://git@github.com/zsimic/uv-metadata.git"

    cli.run(f"-p{runez.SYS_INFO.invoker_python}", "https://github.com/zsimic/uv-metadata@main")
    assert cli.succeeded
    assert '"name": "uv-metadata"' in cli.logged.stdout


def test_sdist_fallback(cli):
    cli.run("pycparser<2.15")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "pycparser"
    assert payload["version"] == "2.14"


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

    cli.run("six<1")
    assert cli.succeeded
    assert "UNKNOWN" not in cli.logged.stdout
    assert '"version": "0.9.2"' in cli.logged.stdout


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

    cli.run(tests_folder / "colorama-0.1.zip")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "colorama"
    assert payload["version"] == "0.1"
    assert payload["top_level"] == ["colorama"]


def test_project_folder(cli):
    project_folder = runez.to_path(cli.project_folder)

    # Exercise an ad-hoc invocation (such as .venv/bin/python <script>), instead of using the regular `bin/` entry point
    cli.run("--help", main=project_folder / "uv_metadata.py")
    assert cli.succeeded
    assert "usage: uv_metadata" in cli.logged.stdout

    # Exercise the "no positional args" case (which looks at current folder by default)
    with runez.CurrentFolder(project_folder):
        cli.run(f"-p{runez.SYS_INFO.invoker_python}")
        assert cli.succeeded
        payload = json.loads(cli.logged.stdout.contents())
        assert payload["entry_points"]["console_scripts"]["uv-metadata"] == "uv_metadata:main"
        assert payload["name"] == "uv-metadata"
        assert payload["top_level"] == ["uv_metadata"]

    cli.run(cli.tests_folder)
    assert cli.failed
    assert "no pyproject.toml or setup.py" in cli.logged


def test_full_flag(cli):
    tests_folder = runez.to_path(cli.tests_folder) / "sample-dist"
    cli.run(tests_folder / "colorama-0.1.zip")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert "description" not in payload

    cli.run("--full", tests_folder / "colorama-0.1.zip")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert "description" in payload


def test_single_key(cli):
    cli.run(cli.project_folder, "-kname")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "uv-metadata"

    cli.run(cli.project_folder, "-kname2")
    assert cli.failed
    assert "no key 'name2' in metadata" in cli.logged
