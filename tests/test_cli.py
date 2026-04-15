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
    assert "no pyproject.toml or setup.py" in cli.logged


def test_dist_info(cli, tmp_path):
    import zipfile

    # Build a minimal .whl and then run against the extracted dist-info
    whl = tmp_path / "sample-1.0-py3-none-any.whl"
    meta = "Metadata-Version: 2.1\nName: sample\nVersion: 1.0\nSummary: A test package\n"
    with zipfile.ZipFile(whl, "w") as zf:
        zf.writestr("sample-1.0.dist-info/METADATA", meta)

    # Test against the .whl file directly
    cli.run(str(whl))
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "sample"
    assert payload["version"] == "1.0"
    assert payload["summary"] == "A test package"

    # Test against an extracted .dist-info folder
    dist_info = tmp_path / "sample-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(meta)
    cli.run(str(dist_info))
    assert cli.succeeded
    payload = json.loads(cli.logged.stdout.contents())
    assert payload["name"] == "sample"


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


def test_single_key(cli):
    cli.run(cli.project_folder, "-kname")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "uv-metadata"

    cli.run(cli.project_folder, "-kname2")
    assert cli.failed
    assert "no key 'name2' in metadata" in cli.logged


def test_bogus(cli):
    cli.run("a--bogus-package-that-does-not-exist--z")
    assert cli.failed
