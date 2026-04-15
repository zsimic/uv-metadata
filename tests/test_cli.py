import json


def test_folder(cli):
    cli.run(cli.project_folder)
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["entry_points"]["console_scripts"]["uv-metadata"] == "uv_metadata:main"
    assert payload["name"] == "uv-metadata"
    assert payload["top_level"] == ["uv_metadata"]

    cli.run(cli.tests_folder)
    assert cli.failed
    assert "no pyproject.toml or setup.py"


def test_package(cli):
    cli.run("pip")
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert "pip" in payload["entry_points"]["console_scripts"]
    assert payload["name"] == "pip"
    assert payload["version"]

    cli.run("coverage", "-khome_page")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "https://github.com/coveragepy/coveragepy"


def test_single_key(cli):
    cli.run(cli.project_folder, "-kname")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "uv-metadata"

    cli.run(cli.project_folder, "-kname2")
    assert cli.failed
    assert "'name2' not found in metadata" in cli.logged


def test_bogus(cli):
    cli.run("a--")
    assert cli.failed
    assert "failed with exit code" in cli.logged
